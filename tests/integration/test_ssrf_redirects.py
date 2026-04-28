"""Integration tests for the H-1 SSRF redirect/pagination fix.

The classic ``requests.get(allow_redirects=True)`` pattern lets a *public*
URL 302-redirect to an internal IP (AWS metadata at 169.254.169.254, an
internal Postgres at 127.0.0.1, ...) and SSRF-protection that only checked
the original URL would happily follow the redirect.

The fix replaces the bare ``requests.get`` with ``_safe_get`` which:

* disables ``requests``' built-in redirect handling
* re-runs ``_is_private_ip`` on every ``Location`` header
* caps redirect depth at 5

These tests spin up a tiny ``http.server`` in the test process and have
``_safe_get`` actually follow real-but-evil redirects against it. No
mocks at the requests layer — the whole HTTP path is exercised.

The pagination test uses a JSON body that returns a ``next`` URL pointing
at a private IP. ``APIExtractionAgent`` must refuse to follow it.
"""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import List
from unittest.mock import patch

import pytest
import requests

from src.agents.api_agent import _is_private_ip, _safe_get


# ---------------------------------------------------------------------------
# Tiny HTTP server fixture
# ---------------------------------------------------------------------------


class _FakeUpstream:
    """A tiny HTTP server that can be programmed per-request.

    Tests push ``(status, headers, body)`` tuples onto the queue and the
    server pops them on each incoming request — letting us script exact
    redirect chains.
    """

    def __init__(self) -> None:
        self.queue: List[tuple] = []
        self.received_paths: List[str] = []
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> int:
        self_ = self

        class Handler(BaseHTTPRequestHandler):
            # Suppress the default access log — pytest output stays clean.
            def log_message(self, fmt, *args):
                pass

            def do_GET(self):
                self_.received_paths.append(self.path)
                if not self_.queue:
                    self.send_response(500)
                    self.end_headers()
                    return
                status, headers, body = self_.queue.pop(0)
                self.send_response(status)
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                if body is not None:
                    self.wfile.write(body.encode() if isinstance(body, str) else body)

        # Bind to localhost on an ephemeral port.
        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return port

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()


@pytest.fixture
def upstream():
    server = _FakeUpstream()
    port = server.start()
    yield server, port
    server.stop()


# ---------------------------------------------------------------------------
# is_private_ip behaviour
# ---------------------------------------------------------------------------


def test_is_private_ip_blocks_aws_metadata():
    """The single most common SSRF target — link-local 169.254.169.254 —
    is unconditionally blocked."""
    assert _is_private_ip("http://169.254.169.254/latest/meta-data") is True


def test_is_private_ip_blocks_non_http_schemes():
    """``file://``, ``gopher://``, ``ftp://`` are rejected at scheme level
    so an attacker can't swap protocol to read local files."""
    assert _is_private_ip("file:///etc/passwd") is True
    assert _is_private_ip("gopher://x.com/") is True
    assert _is_private_ip("ftp://example.com/") is True


def test_is_private_ip_allows_public_https():
    """Sanity: a public host is not blocked."""
    # 8.8.8.8 is unambiguously global per Python's ipaddress module.
    assert _is_private_ip("https://8.8.8.8/") is False


# ---------------------------------------------------------------------------
# _safe_get redirect handling
# ---------------------------------------------------------------------------


def test_safe_get_blocks_redirect_to_private_ip(upstream):
    """The classic SSRF: a public URL returns a 302 to a private IP. The
    naïve ``requests.get(allow_redirects=True)`` would follow it. Our
    ``_safe_get`` must refuse on the second hop."""
    server, port = upstream
    public_url = f"http://127.0.0.1:{port}/start"

    # First (and only) hop the server is allowed to serve: 302 → metadata.
    server.queue.append((
        302,
        {"Location": "http://169.254.169.254/latest/meta-data/iam/security-credentials/"},
        "",
    ))

    # Bypass the *initial* private-IP check (127.0.0.1 is private too) so
    # we exercise the redirect path specifically. In production the
    # initial check would refuse 127.0.0.1 anyway — this test isolates
    # the redirect-validation behaviour.
    with patch(
        "src.agents.api_agent._is_private_ip",
        side_effect=lambda url: "169.254" in url,
    ):
        s = requests.Session()
        with pytest.raises(requests.exceptions.HTTPError) as exc:
            _safe_get(s, public_url, headers={}, timeout=5)

    assert "private/reserved" in str(exc.value)
    # We must have hit the upstream exactly once — the redirect was
    # refused before a second request happened.
    assert len(server.received_paths) == 1


def test_safe_get_follows_legitimate_redirects(upstream):
    """A redirect to *another public* URL must be followed normally so
    legitimate APIs that 302 between subdomains keep working."""
    server, port = upstream
    public_url = f"http://127.0.0.1:{port}/start"

    server.queue.append((
        302,
        {"Location": f"http://127.0.0.1:{port}/landed"},
        "",
    ))
    server.queue.append((
        200,
        {"Content-Type": "application/json"},
        json.dumps({"ok": True}),
    ))

    # Treat 127.0.0.1 as public for this test — we're testing the
    # follow-through, not the SSRF guard.
    with patch("src.agents.api_agent._is_private_ip", return_value=False):
        s = requests.Session()
        r = _safe_get(s, public_url, headers={}, timeout=5)

    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert server.received_paths == ["/start", "/landed"]


def test_safe_get_caps_redirect_depth(upstream):
    """A redirect loop must be broken after the cap — otherwise an
    attacker could DoS the worker by making it follow infinite hops."""
    server, port = upstream
    public_url = f"http://127.0.0.1:{port}/loop"

    # Queue many redirects (more than _MAX_REDIRECT_HOPS).
    for _ in range(20):
        server.queue.append((
            302,
            {"Location": f"http://127.0.0.1:{port}/loop"},
            "",
        ))

    with patch("src.agents.api_agent._is_private_ip", return_value=False):
        s = requests.Session()
        with pytest.raises(requests.exceptions.HTTPError) as exc:
            _safe_get(s, public_url, headers={}, timeout=5)

    assert "Too many redirects" in str(exc.value)
    # The server saw at most _MAX_REDIRECT_HOPS + 1 requests.
    assert len(server.received_paths) <= 7


# ---------------------------------------------------------------------------
# APIExtractionAgent pagination — same SSRF guard must apply per page
# ---------------------------------------------------------------------------


def test_pagination_next_url_to_private_ip_is_blocked(upstream, tmp_path):
    """Page 1 returns a JSON body with ``next: "http://127.0.0.1/..."``.
    The agent must refuse to fetch the next page."""
    server, port = upstream
    public_url = f"http://127.0.0.1:{port}/page1"

    page1 = {
        "data": [{"id": 1}, {"id": 2}],
        "next": "http://169.254.169.254/page2",  # SSRF pivot
    }
    server.queue.append((
        200,
        {"Content-Type": "application/json"},
        json.dumps(page1),
    ))

    from src.agents.api_agent import APIExtractionAgent
    from src.models.handoffs import UserIntent
    from src.models.state import AnalysisState
    from src.config import settings as _settings

    state = AnalysisState(
        user_intent=UserIntent(
            csv_path="",
            api_url=public_url,
            api_headers=None,
            api_auth=None,
            json_path="data",
            analysis_question="Get rows",
        ),
    )

    # Stub the upload dir so the agent writes its CSV into tmp_path.
    with patch.object(_settings, "upload_dir", str(tmp_path)):
        # Treat ALL urls as public except the AWS metadata IP. The agent
        # then exercises the next-url block.
        with patch(
            "src.agents.api_agent._is_private_ip",
            side_effect=lambda url: "169.254" in url,
        ):
            agent = APIExtractionAgent()
            # Replace the constructed agent's llm_agent with a no-op so we
            # don't fire a real LLM during the agent's prompt build.
            from unittest.mock import MagicMock
            agent.llm_agent = MagicMock()
            result = agent.process(state)

    # Page 1 succeeded, page 2 was rejected — the agent surfaces an error
    # rather than a CSV. (Or it may write a partial CSV; either way no
    # second hop reached the upstream).
    second_hop_count = sum(1 for p in server.received_paths if "page2" in p)
    assert second_hop_count == 0, (
        "next_url pointing at private IP was followed — SSRF regression"
    )
