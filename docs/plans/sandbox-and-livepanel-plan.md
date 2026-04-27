# Plan: Sandbox hardening + LivePanel (kill the Jupyter Server container)

**Date**: 2026-04-27
**Project**: Inzyts (`/home/mukan/Documents/Inzyts`)
**Status**: Planning · approved · execution starting
**Goal**: Replace the embedded Jupyter Lab "Live" iframe with a native Inzyts panel using `sandbox_executor`, and harden the sandbox with proper security primitives. Drop the `jupyter` Docker container entirely.

---

## 1. Current state (audit findings)

| Component | What it does today |
|---|---|
| [src/services/sandbox_executor.py](../../src/services/sandbox_executor.py) | Wraps `jupyter_client.start_new_kernel()` — already a "custom kernel" path. Has cell timeout (60s default), output truncation, image size limit (5MB). **No resource limits, no network isolation, no fs confinement, no non-root user enforcement.** Used today by the cell-edit / re-run flow. |
| [src/server/services/jupyter_proxy.py](../../src/server/services/jupyter_proxy.py) | Proxies WebSocket to the Jupyter Server container at port 8888 over `httpx` + `websockets`. Used by the **Live** tab in `NotebookViewer`. |
| [src/server/routes/notebooks.py](../../src/server/routes/notebooks.py) | Owns `/notebooks/...` endpoints. Has `/jupyter-token` (returns the JUPYTER_TOKEN env var to the frontend so it can attach to the Lab iframe). HTML render uses `nbconvert` (server-side). |
| [frontend/src/components/LiveNotebook.tsx](../../frontend/src/components/LiveNotebook.tsx) | Form-submits the JUPYTER_TOKEN into a Jupyter Lab iframe (`VITE_JUPYTER_URL`). Embedded Lab's CSS clashes with Inzyts dark theme. |
| [docker-compose.yml `jupyter` service](../../docker-compose.yml) | Builds Jupyter Lab on port 8888, mounts `src/`, `output/`, datasets. ~2GB memory cap. |

**Security baseline today**: the kernel inherits the worker container's uid (`inzyts` user, no shell, no home dir). The container itself is the sandbox. There is no per-kernel memory/CPU/process cap, no egress block, no per-job tmpdir.

---

## 2. PR 1 — Sandbox hardening + execution API

**Goal**: bring `sandbox_executor` to production-grade isolation and expose a clean API. **Independent of PR 2** — PR 1 is valuable on its own (it secures the existing cell-edit and re-run flow, which today shares the same un-hardened executor).

### 2.1 Tasks

| # | Task | File(s) | Notes |
|---|---|---|---|
| **A1** | Refactor `SandboxExecutor` into a `KernelSandbox` class with explicit `SandboxPolicy` dataclass (memory_mb, cpu_seconds, timeout_seconds, max_processes, max_open_files, network_allowed, working_dir). Default policy = "production" (locked-down). | [src/services/sandbox_executor.py](../../src/services/sandbox_executor.py) | Backwards-compatible: keep the old `SandboxExecutor` class as a thin wrapper that uses the production policy. |
| **A2** | Add `preexec_fn` that calls `resource.setrlimit` for `RLIMIT_AS` (memory), `RLIMIT_CPU` (cpu seconds), `RLIMIT_NPROC` (process count), `RLIMIT_NOFILE` (file descriptors), `RLIMIT_FSIZE` (max file write). `os.setsid` so we own the process group. | sandbox_executor.py | Linux-only; on macOS/Windows the limits silently no-op (acceptable — production runs in Docker on Linux). |
| **A3** | Per-cell hard timeout: track wall-clock since `execute()`, and if exceeded, `os.killpg(pgid, SIGKILL)` rather than the existing soft `interrupt_kernel()`. The kernel can ignore interrupts but cannot ignore SIGKILL. | sandbox_executor.py | Logs a `KERNEL_TIMEOUT_KILL` audit event. |
| **A4** | Working dir confinement: `KernelSandbox(working_dir=...)` defaults to a per-job tmpdir. Kernel `cwd` is set to that dir; bind-mount only `data/uploads/<job>` and `output/<job>` (the rest of the worker FS is reachable but the kernel's `cwd` and a startup `os.chdir()` keep relative paths safe). For absolute paths the only mitigation is the next item. | sandbox_executor.py + worker container | Belt-and-suspenders with #5. |
| **A5** | Network egress block: add `iptables -A OUTPUT -j DROP` in the worker container's entrypoint, with allowlisted exceptions for `db:5432`, `redis:6379`, and the LLM provider host (whitelisted by env). The kernel inherits this. **This is the most important control** — LLM-generated code can't `urllib.request` your data anywhere. | `Dockerfile` (backend target), worker startup script, README threat-model section | Allowlist needs to handle Anthropic/OpenAI/Gemini hostnames. Keeping a small `entrypoint.sh` that wraps the worker process. |
| **A6** | Non-root kernel user: confirm worker container runs as `inzyts` (not root); add a kernel-only `nobody`-equivalent user if we want defence-in-depth. Document threat model: LLM code can read the worker's source mounts (read-only mount), but cannot write outside `output/` and `data/uploads/`. | Dockerfile | Likely already fine — verify and document. |
| **A7** | New REST endpoints in [notebooks.py](../../src/server/routes/notebooks.py): `POST /notebooks/{job_id}/cells/execute` (one cell, returns 202 + execution_id), `POST /notebooks/{job_id}/cells/restart` (kill + start kernel), `POST /notebooks/{job_id}/cells/interrupt` (signal current cell). | notebooks.py | All require `verify_token`. Cell payload is `{"code": "..."}`. |
| **A8** | New WS event types emitted from Celery worker through SocketIO: `cell_status` (running/idle/error), `cell_output` (stdout/stderr/display_data/execute_result chunks), `cell_complete` (with execution_count + final error). Each carries `execution_id`. | New `src/server/services/cell_stream.py` + emitter wiring in `engine.py` | Frontend subscribes via the existing `useSocket`. |
| **A9** | Persistent kernel pool keyed by `job_id`: `KernelPool` class spins up a kernel on first execute for a job, reuses it for subsequent cells, gc's after 30 min idle. | Pool in `src/services/sandbox_executor.py` | Shared by cell-edit, re-run, and the new Live API. |
| **A10** | Audit logging: every cell execution writes a `CellExecutionAudit` row (job_id, user_id, code_hash, exit_status, duration_ms, killed_reason). | `src/server/db/models.py` + Alembic migration | Investigation aid if a kernel kills/leaks. |
| **A11** | Tests: each security primitive has a black-box test that proves the limit fires. Memory bomb → MemoryError. Fork bomb → blocked. Network → `urlopen` fails. CPU loop → killed at timeout. Path escape → restricted. | `tests/unit/services/test_sandbox_security.py` (new) | All must run in <10s combined. |
| **A12** | Update `docs/architecture.md`: new "Threat Model" section listing what's defended and what's not (e.g. timing side-channels are out-of-scope). | docs/architecture.md | Cross-reference this plan. |

### 2.2 Backwards compatibility

- The existing `SandboxExecutor(...)` constructor signature is preserved as a wrapper around `KernelSandbox(policy=production_policy)`. Cell-edit agent and re-run flow keep working without changes.
- New endpoints are additive — `/jupyter-token` and the WS proxy still work in PR 1 (deleted in PR 2).
- No DB schema break beyond the additive `cell_execution_audit` table.

### 2.3 Acceptance criteria

- [ ] All existing 1091 backend tests pass.
- [ ] New sandbox-security test suite passes — every primitive proves it kills bad code.
- [ ] Manual: kick off a cell-edit on an existing job, verify it still works through `KernelSandbox` (i.e., no regression in agent flow).
- [ ] Manual: create a cell that does `import urllib.request; urllib.request.urlopen('http://example.com')` — must fail with a network error inside the worker container.
- [ ] Manual: cell that does `[0] * (10**9)` — killed by RLIMIT_AS, kernel auto-restarts, audit row written.

---

## 3. PR 2 — LivePanel + Jupyter removal

**Goal**: replace the iframe-embedded Jupyter Lab with a native panel that matches the Command Center design. Then drop the `jupyter` container.

### 3.1 Tasks

| # | Task | File(s) | Notes |
|---|---|---|---|
| **B1** | Define output-renderer interface: `interface CellOutput { output_type: 'stream' \| 'display_data' \| 'execute_result' \| 'error'; data?: Record<string, string>; text?: string; ename?: string; evalue?: string; traceback?: string[] }`. MIME-type → component map: `text/plain` → mono pre, `image/png` → `<img>`, `text/html` → safe HTML (DOMPurify), `application/json` → JSON tree, `application/vnd.plotly.v1+json` → plotly.js. | new `frontend/src/components/command-center/panels/live/types.ts` and `outputRenderers.tsx` | Plotly is the heaviest renderer; lazy-load it. |
| **B2** | Build `LivePanel.tsx` skeleton: header (Status pill + Run all + Restart kernel + Interrupt), cell list (read from job's notebook cells via existing `getNotebookCells`), per-cell controls (Run / Stop). | `frontend/src/components/command-center/panels/live/LivePanel.tsx` | Uses Inzyts dark-theme tokens. |
| **B3** | Output rendering components: `TextOutput`, `ErrorOutput` (formatted traceback), `ImageOutput`, `HtmlOutput` (DOMPurify-sanitised), `DataFrameOutput` (renders the pandas-generated `text/html` as a styled table), `PlotlyOutput` (lazy import). | `frontend/src/components/command-center/panels/live/outputs/` | One file per renderer. |
| **B4** | WS subscription for `cell_status` / `cell_output` / `cell_complete` events. Add to `useSocket` (one socket connection per job). Keyed by `execution_id` so concurrent cells route correctly. | `frontend/src/hooks/useSocket.ts` | Cell output is appended in-place — never overwrites prior outputs. |
| **B5** | Wire LivePanel into the existing `NotebookViewer` — replace the `LiveNotebook` import with `LivePanel`. Remove the iframe form-submit dance. | `frontend/src/components/NotebookViewer.tsx` | Visual / Static / Interactive tabs unchanged; just the Live tab content swaps. |
| **B6** | Drop `jupyter` service from [docker-compose.yml](../../docker-compose.yml). Drop `jupyter` Dockerfile target. Reduce image build time and stack memory by ~2GB. | docker-compose.yml, Dockerfile | One less container. |
| **B7** | Delete `src/server/services/jupyter_proxy.py` and the `/notebooks/jupyter-token` endpoint. | notebooks.py | All consumers gone after B5. |
| **B8** | Remove `VITE_JUPYTER_URL` env var, `JUPYTER_TOKEN` env var (or keep as internal-only sandbox token), `INZYTS__JUPYTER__*` settings. | .env.example, vite-env.d.ts, settings module | Audit log: search for `JUPYTER_` and prune dead references. |
| **B9** | Delete the now-unused `frontend/src/components/LiveNotebook.tsx` and `getJupyterToken` API method. | LiveNotebook.tsx, api.ts | Frontend bundle shrinks. |
| **B10** | LivePanel tests: Run-cell triggers POST + WS subscription; cell output renders correctly per MIME type; error output formats traceback; Restart kernel sends POST and clears output state. | `LivePanel.test.tsx` | RTL + msw / vi.fn() for the API client. |
| **B11** | Update README + docs/architecture.md: drop "Jupyter Lab Live tab" reference, add "Native Live notebook panel" section. Update agent count / phase model are already correct from earlier work. | README.md, docs/architecture.md | Small edits. |

### 3.2 Acceptance criteria

- [ ] `docker compose ps` shows 5 services (was 6); jupyter is gone.
- [ ] Live tab renders cells in the Inzyts dark theme — no Jupyter-Lab CSS bleed.
- [ ] Run-cell button executes via the PR 1 API; output streams in via WS within ~200ms.
- [ ] Memory bomb / fork bomb / network call still blocked (PR 1 primitives carry over).
- [ ] All frontend tests pass; tsc clean; production build clean and ≤ +30 KB gzipped vs. main.
- [ ] No `JUPYTER_TOKEN` or `VITE_JUPYTER_URL` references remain in the working tree (audited via grep).

### 3.3 Rollback

- The `jupyter` container removal is reversible (one git revert), but data on its mounts is gone. Since Jupyter just runs against `output/` and `data/uploads/`, and those are bind-mounted from the host, **no data loss**.
- If LivePanel has a critical bug in the field, `git revert` on the LivePanel commit puts the iframe back. The PR 1 sandbox hardening stays.

---

## 4. Phasing & sequencing

```
PR 1
└── Phase A — Sandbox core
    ├── A1  KernelSandbox class + SandboxPolicy
    ├── A2  resource.setrlimit
    ├── A3  process-group SIGKILL on timeout
    ├── A4  working dir confinement
    ├── A6  non-root kernel user (verify)
    └── A11 Security tests (gate for landing)
└── Phase B — Network egress
    └── A5  iptables egress block + allowlist
└── Phase C — API + audit
    ├── A7  REST endpoints
    ├── A8  WS events
    ├── A9  KernelPool
    └── A10 CellExecutionAudit table + migration
└── Phase D — Docs
    └── A12 Threat model in architecture.md

PR 2
└── Phase E — Renderers
    ├── B1  Output-renderer types + MIME map
    └── B3  Renderer components
└── Phase F — UI shell
    ├── B2  LivePanel skeleton
    └── B4  WS subscription wiring
└── Phase G — Cutover
    ├── B5  Replace iframe in NotebookViewer
    ├── B7  Delete jupyter_proxy.py + /jupyter-token
    └── B9  Delete LiveNotebook.tsx + getJupyterToken
└── Phase H — Container removal
    ├── B6  Drop jupyter service from docker-compose + Dockerfile
    └── B8  Remove env vars
└── Phase I — Polish
    ├── B10 LivePanel tests
    └── B11 README + architecture.md
```

---

## 5. Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| iptables egress block bricks legit pip-install / LLM calls in the worker container | Medium | High | Allowlist Anthropic/OpenAI/Gemini hostnames; smoke test before merging A5. The kernel runs in the worker container, so the kernel inherits the rules — but the LLM agent code also runs there and must reach the provider. |
| RLIMIT_AS too tight → kills legitimate analyst workflows on large datasets | Medium | Medium | Default to 2 GB (matches typical Docker memory cap); make it a `SandboxPolicy` parameter so per-job upgrades are easy. |
| KernelPool leaks kernels if cleanup races with cell execution | Low | Medium | Idle-gc with explicit job_id → kernel mapping; on worker restart, kill all known kernels first thing. |
| LivePanel's plotly renderer balloons bundle size | Medium | Low | Lazy-import (`React.lazy`); Plotly only loads on first plotly cell. |
| `nbconvert` HTML output (used today) trusts the notebook source — could XSS | Low | Medium | DOMPurify on all `text/html` outputs (renderer side). Document in threat model. |
| Cell-edit agent breaks when SandboxExecutor switches to KernelSandbox | Medium | Medium | Keep the wrapper class with the same signature; cover with the existing cell-edit tests. |

---

## 6. Out of scope

- Multi-user kernel sharing (one kernel per job; users are the analyst running the job).
- gVisor or Firecracker isolation (production-grade VM-level sandbox; meaningful next step but a separate epic).
- Jupyter widgets (`ipywidgets`) — not required; analysts get cell outputs only.
- Magic commands (`%matplotlib inline`, `%timeit`, etc.) — kernel still supports them; renderer just shows the resulting outputs.
- Importing/uploading new notebooks (analysts operate on the system-generated notebook only).

---

## 7. Open questions

1. **Egress allowlist mechanism**: do we have a single LLM provider host per deploy, or do we support runtime-configurable providers? The allowlist needs to track that.
2. **CellExecutionAudit retention**: how long do we keep these rows? Default proposal: 90 days, then prune via a periodic task.
3. **Plotly renderer**: confirm the codegen agents actually emit `application/vnd.plotly.v1+json` outputs today. If they emit static images instead, the plotly renderer is unnecessary.

These can be settled as we hit them.
