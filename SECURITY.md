# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Inzyts, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please email the maintainer directly or use [GitHub's private vulnerability reporting](https://github.com/kamuma03/Inzyts/security/advisories/new).

We will acknowledge your report within 48 hours and aim to provide a fix within 7 days for critical issues.

## Security Considerations

### API Keys and Secrets

- **Never commit API keys or secrets** to the repository
- Use the `.env` file for local development (already in `.gitignore`)
- See `config/.env.example` for the expected environment variables
- Generate tokens with: `python -c "import secrets; print(secrets.token_hex(32))"`

### Sandbox Execution

Inzyts executes LLM-generated code in a sandboxed environment with:
- Isolated namespace (no access to the host file system)
- Allowlisted imports only
- 60-second timeout per cell execution
- No network access from sandbox

### Authentication

- JWT-based login with bcrypt password hashing (`POST /api/v2/auth/login`)
- System API token (`INZYTS_API_TOKEN`) for worker/server-to-server calls, verified with `secrets.compare_digest` (constant-time)
- `ADMIN_PASSWORD` is required — the server refuses to start without it (no default value)
- JWT tokens stored in `sessionStorage` only (cleared on tab/browser close)
- JWT claims include `sub` (username) and `role` for stateless authorization
- Token expiry configurable via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default: 7 days)

### Role-Based Access Control (RBAC)

- Three-tier role hierarchy: **Admin** > **Analyst** > **Viewer**
- Roles stored in the `users` table (`role` column, PostgreSQL enum) and embedded in JWT claims
- `require_role()` FastAPI dependency factory enforces role checks with hierarchy awareness — admins automatically pass analyst-level checks
- First-boot admin auto-creation assigns the `admin` role automatically
- System API tokens receive `admin` role for full access
- **Analyst+ endpoints** (mutations / spend): `/api/v2/analyze`, `/api/v2/files/upload`, `/api/v2/files/upload_batch`
- **Admin-only endpoints**: user management (`/api/v2/admin/users`), audit log queries (`/api/v2/admin/audit-logs`)
- Frontend routes guarded by role-based route components; admin navigation only visible to admin users

### Per-Job Ownership (Object-Level Authorization)

In addition to role gates, every per-job endpoint enforces **owner-or-admin** access via the shared `src.server.db.queries.resolve_owned_job` helper:

- Non-admin users can only read, mutate, or stream jobs where `Job.user_id == user.id`. Cross-user access returns `404 Job not found` (not `403`) to avoid id enumeration.
- Legacy jobs with `user_id IS NULL` (created before the `user_id` column was added) are admin-only.
- The check is applied uniformly to every `/notebooks/*`, `/reports/*`, `/jobs/*` route handler and the Socket.IO `join_job` subscription.
- WebSocket sessions stash `user_id` and `role` at handshake time; subsequent `join_job` calls reject rooms the user does not own.

### Login Brute-Force Protection

- `/api/v2/auth/login` is rate-limited to **10 requests/minute per source IP** (via `slowapi`) on top of the bcrypt cost.
- All failed attempts are written to the audit log with the supplied username and source IP for forensic review.
- Constant-time comparison against a dummy hash is used when the user does not exist, so response time does not leak username validity.

### Audit Logging

- All security-relevant actions are recorded in the `audit_logs` database table:
  - **Authentication**: successful logins, failed login attempts (with IP and username)
  - **Data operations**: analysis starts, file uploads, job cancellations
  - **User management**: user creation, role changes, account deactivation, deletion
- Each audit entry includes: timestamp, user ID, username, action, resource type/ID, detail, IP address, HTTP method/path, and status code
- `AuditMiddleware` (Starlette middleware) auto-logs API requests to security-relevant endpoints
- `record_audit()` async helper provides fine-grained logging from route handlers
- Audit log failures are caught and logged — they never break the request flow
- Admin-only query endpoint with filters: username, action type, date range
- IP extraction supports `X-Forwarded-For` headers for reverse proxy deployments

### SQL Database Security

- **All** SQL paths validate the query via `sqlglot` AST parsing — only `SELECT` statements permitted (CTE-embedded DML is also rejected). The validator lives in `src.utils.db_utils.validate_select_only` and is shared by:
  - The autonomous SQL extraction agent (`src.agents.sql_agent`)
  - The explicit `db_query` ingestion path (`src.server.services.data_ingestion.ingest_from_sql`)
  - The `/api/v2/files/sql-preview` endpoint
- Database connections enforce read-only transactions (`SET TRANSACTION READ ONLY`) on every backend that supports it (PostgreSQL, MySQL) as defense-in-depth.
- URI scheme allowlist: `postgresql`, `mysql`, `mssql`, `bigquery`, `snowflake`, `redshift`, `databricks+connector` — `sqlite://` is blocked.
- URI **host** allowlist: loopback (`127.0.0.0/8`, `::1`, `localhost`), link-local (`169.254.0.0/16`, including AWS metadata), and platform-internal docker hostnames (`db`, `redis`, plus `INZYTS_INTERNAL_HOSTS`) are blocked. Override with `INZYTS_DB_URI_ALLOW_LOOPBACK=1` for local dev.
- Results capped at `SQL_MAX_ROWS` (default 200,000) and `SQL_MAX_COLS` (default 500).

### Cloud Storage Security

- Cloud URI scheme allowlist: `s3://`, `gs://`, `az://`, `abfs://`, `abfss://` only — `http://`, `ftp://`, `file://` are rejected
- Cloud credentials are never stored or accepted in the URI — they must be configured via environment variables (`AWS_ACCESS_KEY_ID`, `GOOGLE_APPLICATION_CREDENTIALS`, `AZURE_STORAGE_CONNECTION_STRING`)
- File size limit enforced before download (`CLOUD_MAX_FILE_SIZE`, default 500 MB) to prevent resource exhaustion
- Downloaded files are placed in the upload directory with restricted permissions

### REST API Data Extraction Security

- **SSRF Protection**: All API URLs are resolved to IP addresses and checked against private/reserved ranges (RFC 1918, link-local, multicast); requests to internal networks are blocked.
- **Per-hop validation** — `requests` redirect-following is disabled and replaced with a manual loop (`_safe_get`) that re-runs the SSRF check on every `Location` header, capped at 5 redirects. This blocks the classic 302-to-internal-IP pivot.
- **Pagination guarded** — every paginated `next_url` (whether from JSON body or `Link` header) is re-validated before the next request, so an attacker-controlled response cannot pivot to a private IP after the first hop.
- **Scheme allowlist** — only `http://` and `https://` URLs are accepted; `file://`, `gopher://`, `ftp://` are rejected at validation time.
- `localhost`, `127.0.0.1`, and all loopback/private addresses are blocked — no exemptions, even for development.
- Response size capped at `API_MAX_RESPONSE_SIZE` (default 100 MB).
- Request timeout enforced (`API_TIMEOUT`, default 30 seconds) to prevent hanging connections.
- Authentication credentials (Bearer tokens, API keys, Basic auth) are passed via headers only — never logged or persisted.

### PII Detection & Report Security

- **PII Detection Service**: Regex-based scanner identifies emails, US phone numbers, SSNs, credit card numbers, and IP addresses in notebook content (markdown cells, code source, and code outputs)
- PII findings are deduplicated and partially masked in scan results (e.g., `j***@example.com`, `***-**-6789`) so sensitive data is not fully exposed in the API response
- Common/safe IPs (127.0.0.1, 0.0.0.0, etc.) are excluded from PII findings to reduce false positives
- **Optional PII Masking**: Report export supports `include_pii_masking` flag that replaces all detected PII with redacted placeholders (`[EMAIL]`, `[SSN]`, `[PHONE]`, etc.) before rendering
- PII scan is informational — it never blocks report generation or analysis execution
- Report files are written to `{output_dir}/reports/` alongside existing notebook output

### Credential & Error Handling

- Log messages emitted to WebSocket clients are automatically scrubbed of database URI credentials and API keys/tokens
- API error responses never expose internal details (stack traces, file paths) — errors are logged server-side only
- Password verification failures are logged at WARNING level for security monitoring

### Frontend Security

- All markdown rendered via `dangerouslySetInnerHTML` is sanitized with DOMPurify using a strict tag/attribute allowlist
- Frontend validates DB URI schemes against an allowlist before submission
- File path inputs reject colon characters to prevent URI-based attacks

### Docker Deployment

- Database (5432) and Redis (6379) ports are bound to `127.0.0.1` by default — not exposed externally
- Services are isolated across two Docker networks (`backend` and `db`)
- All services have memory limits enforced via Docker resource constraints
- Backend includes a healthcheck; frontend waits for backend health before starting
- Restart policy is `on-failure:5` to prevent infinite restart loops
- Upload directory has restricted permissions (`chmod 750`)
- Jupyter containers run as non-root (`jovyan` user)
- Use a reverse proxy (e.g., nginx) with TLS for public-facing deployments

### Kernel Bootstrap Security

- Dataset paths are passed to Jupyter kernels via the kernel-subprocess `env` (using the `extra_env` argument on `KernelSandbox`/`SandboxExecutor`), **not** by mutating the worker process's own `os.environ` and **not** by string interpolation. This avoids:
  - Code injection from crafted filenames containing quote characters.
  - Cross-job env leakage where Job B sees Job A's most-recent dataset path in `os.environ`.
- Kernel sessions use LRU eviction when the session limit is reached (graceful degradation instead of hard errors).

### Sandbox `_killpg` Safety Invariants

`KernelSandbox._killpg()` is called when a cell exceeds its wall-clock timeout. Sending `SIGKILL` to a process group is high-risk: a misresolved `pgid` can take down the worker, the user's shell, or the entire desktop session. Three invariants are checked before any signal is sent:

1. **`pgid != own_pgid`** — refuse to kill the parent's process group. If `setsid()` somehow failed in the kernel child, the resolved pgid will match the parent's. We log an error and fall back to `os.kill(pid, SIGKILL)` on the original PID only.
2. **`pgid == pid`** — a successful `os.setsid()` makes the child the leader of a new session, so its pgid equals its pid. Any mismatch means either `setsid` failed or the PID was reused after the liveness check (kernel exited and Linux reassigned the PID to an unrelated process). Either way, refuse the killpg and SIGKILL the original PID instead.
3. **`setsid()` failure is fatal in the child** — `_build_preexec_fn` no longer swallows `OSError` from `setsid()`. If it fails, the child writes a marker to stderr and calls `os._exit(127)` immediately. Leaving the child in the parent's process group is not safe under any condition.

Without these guards, a single failed `setsid()` followed by a wall-clock timeout could SIGKILL the entire user session. Real-kernel tests (`tests/unit/services/test_sandbox_security.py`) are gated behind a `slow` pytest marker and skipped by default for the same reason — opt in with `pytest -m slow` only after reading `src/services/sandbox_executor.py`.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.10.0  | Yes       |
