#!/bin/sh
set -e

# Ensure writable directories exist and are owned by the app user.
# Bind-mounted host directories may arrive as root-owned; fix that
# on every boot so the non-root "inzyts" process can write to them.
for dir in /app/logs /app/logs/jobs /app/output /app/data/uploads; do
    mkdir -p "$dir"
    chown -R inzyts:inzyts "$dir"
done

# ── Network isolation (default ON) ───────────────────────────────────────
#
# Strict mode is the default — installs an iptables OUTPUT chain that
# drops egress to anything not on the allowlist:
#   * loopback
#   * established/related connections
#   * DNS (so allowlist hostnames stay resolvable at runtime)
#   * docker-internal services (db, redis, plus any names in
#     INZYTS_INTERNAL_HOSTS)
#   * LLM provider API hostnames (default Anthropic / OpenAI / Gemini,
#     overridable via INZYTS_EGRESS_ALLOWLIST)
#   * host.docker.internal when INZYTS__LLM__DEFAULT_PROVIDER=ollama OR
#     INZYTS_ALLOW_HOST_DOCKER_INTERNAL=1
#
# This is the production-grade complement to the proxy-blackhole layer
# applied per-kernel by SandboxPolicy. The proxy block stops casual
# urllib/requests egress; iptables stops raw-socket egress that bypasses
# Python's proxy env vars.
#
# Opt out: set INZYTS_NETWORK_ISOLATION=off in .env.
#
# Requirements (already met by docker-compose.yml):
#   * Container started with cap_add: [NET_ADMIN]
#   * iptables binary in the image (Dockerfile installs it)
#
# Graceful degradation: if iptables is missing or NET_ADMIN isn't granted,
# logs a warning and continues without isolation rather than failing
# startup. The proxy-blackhole layer in SandboxPolicy still applies.
#
# Caveat: kernel subprocesses run in the same network namespace as the
# worker, so the kernel inherits the same allowlist. An attacker could
# still attempt to send data to allowlisted hosts (e.g. craft a POST to
# api.anthropic.com with payload in the body) — without a valid API key
# (stripped from kernel env), the bound is meaningful but not absolute.
# True per-uid scoping is a future enhancement that runs the kernel as
# a separate user.
if [ "${INZYTS_NETWORK_ISOLATION:-strict}" != "off" ]; then
    if ! command -v iptables >/dev/null 2>&1; then
        echo "[entrypoint] WARN: network isolation requested but iptables binary not found"
        echo "[entrypoint]       proxy-blackhole still applies; raw-socket egress NOT blocked"
    elif ! iptables -L OUTPUT >/dev/null 2>&1; then
        echo "[entrypoint] WARN: network isolation requested but iptables not usable"
        echo "[entrypoint]       (container needs cap_add: [NET_ADMIN])"
        echo "[entrypoint]       proxy-blackhole still applies; raw-socket egress NOT blocked"
    else
        echo "[entrypoint] Applying network egress allowlist (default ON; set INZYTS_NETWORK_ISOLATION=off to disable)..."

        iptables -P OUTPUT ACCEPT
        iptables -F OUTPUT

        iptables -A OUTPUT -o lo -j ACCEPT
        iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
        iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
        iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT

        # Internal docker-network targets: db, redis, plus user overrides.
        for host in db redis ${INZYTS_INTERNAL_HOSTS}; do
            ip=$(getent hosts "$host" 2>/dev/null | awk '{print $1}' | head -1)
            if [ -n "$ip" ]; then
                iptables -A OUTPUT -d "$ip" -j ACCEPT
                echo "[entrypoint]   internal: $host -> $ip"
            else
                echo "[entrypoint]   internal: $host (unresolved; skipping)"
            fi
        done

        # LLM provider hosts (resolved at startup; restart container if IPs rotate).
        LLM_HOSTS="${INZYTS_EGRESS_ALLOWLIST:-api.anthropic.com api.openai.com generativelanguage.googleapis.com}"
        for host in $LLM_HOSTS; do
            for ip in $(getent ahosts "$host" 2>/dev/null | awk '{print $1}' | sort -u); do
                iptables -A OUTPUT -d "$ip" -j ACCEPT
                echo "[entrypoint]   llm:      $host -> $ip"
            done
        done

        # Auto-allow host.docker.internal when Ollama is the configured
        # default provider, OR when explicitly requested via env. Skips
        # silently if the host isn't resolvable (e.g. on Linux without
        # extra_hosts: host-gateway).
        OLLAMA_PROVIDER="${INZYTS__LLM__DEFAULT_PROVIDER}"
        if [ "$OLLAMA_PROVIDER" = "ollama" ] || [ -n "${INZYTS_ALLOW_HOST_DOCKER_INTERNAL}" ]; then
            ip=$(getent hosts host.docker.internal 2>/dev/null | awk '{print $1}' | head -1)
            if [ -n "$ip" ]; then
                iptables -A OUTPUT -d "$ip" -j ACCEPT
                echo "[entrypoint]   ollama:   host.docker.internal -> $ip"
            fi
        fi

        # Default DROP for anything not on the allowlist.
        iptables -A OUTPUT -j DROP
        echo "[entrypoint] Network egress allowlist active."
    fi
else
    echo "[entrypoint] Network isolation explicitly disabled (INZYTS_NETWORK_ISOLATION=off)"
fi

# Auto-apply Alembic migrations when launching the API. Runs before uvicorn
# binds the port, so the healthcheck only passes after the schema is current.
# Gated on `uvicorn` so the worker (same image, `celery ...`) doesn't race.
if [ "$1" = "uvicorn" ]; then
    echo "[entrypoint] Running alembic upgrade head..."
    gosu inzyts env HOME=/app alembic upgrade head
fi

# Drop privileges and exec the real command.
# gosu resets HOME to the passwd entry (/home/inzyts) which doesn't exist.
# Wrap via sh -c so we can force HOME=/app after gosu drops privileges.
exec gosu inzyts env HOME=/app "$@"
