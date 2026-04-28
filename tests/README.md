# Inzyts Test Suite

Top-level pytest suite for the Inzyts multi-agent data analysis system.

## Quick Start

```bash
# Run the default unit + collect set (skips ui/integration/e2e/slow by default)
pytest

# Use the test runner for grouped suites
./tests/run_tests.sh                  # all (with default skips)
./tests/run_tests.sh -s unit
./tests/run_tests.sh -s integration
./tests/run_tests.sh -s security
./tests/run_tests.sh -s db            # real Postgres via testcontainers (Docker)
./tests/run_tests.sh -s ui            # Playwright (requires app running)

# Generate HTML coverage report
./tests/run_tests.sh --html
```

`pytest` discovery and default skips are configured in `pyproject.toml` under `[tool.pytest.ini_options]`. By default the runner skips `tests/ui`, `tests/integration`, `tests/e2e`, and the `slow` marker (real-kernel sandbox tests). Opt in explicitly when you need them.

## Test Structure

```
tests/
├── README.md                      # This file
├── conftest.py                    # Root conftest — auto-starts Redis Docker container
├── run_tests.sh                   # Bash runner for grouped suites
├── run_tests.ps1                  # PowerShell equivalent
│
├── unit/                          # Fast, isolated tests — default pytest target
│   ├── agents/                    # Per-agent process() tests (phase1, phase2, extensions)
│   ├── models/                    # Pydantic handoffs, state, profile-lock, cells
│   ├── services/                  # Sandbox executor, kernel session manager,
│   │                              #   PII detector, killpg safety, kernel env
│   │                              #   isolation, template/dictionary/data-loader
│   ├── server/
│   │   ├── routes/                # Per-route handler tests
│   │   ├── services/              # Engine, data ingestion (incl. SELECT-only)
│   │   └── middleware/            # Auth, audit, RBAC
│   ├── utils/                     # DB URI host blocklist, path validators
│   ├── workflow/                  # Graph nodes, routing, rollback
│   └── test_*.py                  # Top-level unit tests (config, llm, errors, …)
│
├── integration/                   # Multi-module flows (real DB / Redis / HTTP)
│   ├── conftest.py                # testcontainers Postgres fixture (session-scoped)
│   ├── test_idor_cross_user.py
│   ├── test_login_rate_limit.py
│   ├── test_role_based_access.py
│   ├── test_ssrf_redirects.py
│   ├── test_sql_real_db.py        # 23 tests against real Postgres 🐘
│   └── test_*.py                  # API, cache, e2e workflow, multi-file, …
│
├── e2e/                           # Full pipeline runs (CSV → notebook)
├── ui/                            # Backend-driven Playwright smoke tests
├── performance/                   # Benchmarks
│
├── security/                      # Input validation, sandbox-escape attempts
├── safety/                        # Prompt-injection / instruction-override resistance
├── contracts/                     # OpenAPI Schemathesis property-based fuzzing
├── accessibility/                 # WCAG scaffolding for backend HTML
│
├── scripts/                       # Verification helpers (not auto-discovered)
├── test_data_multifile/           # Multi-file dataset fixtures
└── fixtures/                      # iris.csv, Bank_Churn.csv, sample_data, expected_notebooks
```

Frontend Playwright tests live under `frontend/tests/`:
- `frontend/tests/e2e/` — critical-journey tests with page-object models
- `frontend/tests/a11y/` — axe-core WCAG 2.1 AA scans

Mutation testing config (security-critical helpers only) lives in `setup.cfg` under `[mutmut]`.

## Test Markers

| Marker | Purpose |
|--------|---------|
| `requires_redis` | Tests that need a running Redis instance |
| `requires_db` | Tests that need a real Postgres (via testcontainers) |
| `slow` | Tests that spawn real Jupyter kernels — opt in with `pytest -m slow` only after reading the safety guarantees in `src/services/sandbox_executor.py` |

## Running Tests

### Test Runner Suites

`./tests/run_tests.sh -s <suite>` accepts:

| Suite | Path |
|-------|------|
| `all` | `tests/` |
| `unit` | `tests/unit/` |
| `integration` | `tests/integration/` |
| `db` | `tests/integration/test_sql_real_db.py` (Docker required) |
| `performance` | `tests/performance/` |
| `ui` | `tests/ui/` (app must be running) |
| `security` | `tests/security/` |
| `safety` | `tests/safety/` |
| `contracts` | `tests/contracts/` |
| `accessibility` | `tests/accessibility/` |
| `workflow` | `tests/unit/workflow/` |
| `models` | `tests/unit/models/` |
| `agents` | `tests/unit/agents/` |
| `services` | `tests/unit/services/` |
| `notebooks` | `tests/integration/test_api_notebooks.py` |
| `notebook-execution` | live-cell execution tests |
| `multi-file` | multi-file dataset tests |
| `templates` | template-manager tests |
| `e2e` | `tests/e2e/` |
| `priority1` / `priority2` | curated subsets |
| `advanced-features` | dimensionality + quality |

Run `./tests/run_tests.sh --help` (or `.ps1 -h`) for the full flag list.

### Direct pytest

```bash
# All non-skipped tests with coverage
pytest --cov=src --cov-report=term-missing

# A single file / class / function
pytest tests/unit/workflow/test_graph_workflow.py
pytest tests/unit/workflow/test_graph_workflow.py::TestInitializeNode
pytest tests/unit/workflow/test_graph_workflow.py::TestInitializeNode::test_initialize_node_success

# Real DB tests (Docker required, requires_db marker)
pytest tests/integration/test_sql_real_db.py -m requires_db

# Slow tests (real kernel sandbox)
pytest -m slow

# Parallel (install pytest-xdist)
pytest -n auto
```

## Writing Tests

Use the AAA pattern (Arrange / Act / Assert). Keep unit tests fast (<1s each), no real I/O, no real subprocesses.

### Mocking guidance

**Mock**: external LLMs, network, filesystem boundaries, time, randomness.

**Do not mock**:
- Database read-only enforcement (mocks can't verify `SET TRANSACTION READ ONLY` actually blocks writes) — use `tests/integration/test_sql_real_db.py` style
- Row-limit truncation (mocks bypass the real `pd.read_sql(..., chunksize=N)` path)
- Connection pool cleanup (mocks can't detect leaked connections)
- Internal logic, pure functions, simple data structures

For sandbox/kernel tests, mock `KernelSandbox` / `SandboxExecutor` unless the test is explicitly marked `slow`. Real-subprocess tests must keep the killpg safety guarantees from `src/services/sandbox_executor.py` in mind.

## Troubleshooting

**Tests not found / import errors**
```bash
cd /path/to/Inzyts
pip install -r requirements.txt
pip install pytest pytest-cov pytest-mock
```
Pytest's `pythonpath = ["."]` is set in `pyproject.toml`; you should not need to export `PYTHONPATH` manually.

**Coverage too low**
```bash
pytest --cov=src --cov-report=term-missing  # see uncovered lines
pytest --cov=src --cov-report=html          # open htmlcov/index.html
```

**UI tests failing**
```bash
./start_app.sh                             # terminal 1
curl http://localhost:5173                  # confirm frontend
curl http://localhost:8000/health           # confirm backend
python -m playwright install chromium
pytest tests/ui --headed --slowmo 1000      # debug visually
```

**Database integration tests failing**
```bash
docker info                                 # confirm Docker is running
pip install "testcontainers[postgres]"
pytest tests/integration/test_sql_real_db.py -m requires_db
```

**Slow tests killing your shell**
The `slow` marker runs real kernels and exercises `setrlimit` + `setsid` + `killpg`. A bad test in this set can SIGKILL the parent process group. Read the safety notes in `src/services/sandbox_executor.py` first, then run with care.

## CI

GitHub Actions runs on push and pull request from `.github/workflows/test.yml`. The workflow installs dependencies, runs `pytest` with coverage, and uploads artifacts.

For local pre-commit, the simplest reasonable hook is:
```bash
./tests/run_tests.sh -s unit --quick
```

## Related

- Architecture: [`../docs/architecture.md`](../docs/architecture.md)
- Security posture: [`../SECURITY.md`](../SECURITY.md)
- Mutation testing: see `[mutmut]` in `../setup.cfg`
- Tool config (pytest, ruff, mypy): `../pyproject.toml`
