# Inzyts — Software Requirements Specification (SPEC)

**Document Version:** 0.1.0
**Baseline:** v0.10.0
**Last Updated:** 2026-05-04
**Status:** Living document — superseded only by future revisions of this file
**Authoritative for:** functional + non-functional requirements
**Complementary to:** [architecture.md](architecture.md) (high-level system design), [README.md](../README.md) (orientation), [SECURITY.md](../SECURITY.md) (operational security posture), [FUTURE_ROADMAP.md](FUTURE_ROADMAP.md) (12-month strategic plan)

---

## Table of Contents

1. [Document Overview](#1-document-overview)
2. [Stakeholders & Personas](#2-stakeholders--personas)
3. [System Context](#3-system-context)
4. [Functional Requirements](#4-functional-requirements)
   - 4.1 [Authentication & Authorization](#41-authentication--authorization-fr-auth)
   - 4.2 [Analysis Initiation](#42-analysis-initiation-fr-analysis)
   - 4.3 [Job Management](#43-job-management-fr-job)
   - 4.4 [File & Data-Source Handling](#44-file--data-source-handling-fr-data)
   - 4.5 [Workflow Orchestration](#45-workflow-orchestration-fr-wf)
   - 4.6 [Agents & Analysis Modes](#46-agents--analysis-modes-fr-agent)
   - 4.7 [Sandbox Execution](#47-sandbox-execution-fr-sbx)
   - 4.8 [Profile Lock & Cache](#48-profile-lock--cache-fr-cache)
   - 4.9 [Notebook & Cell Operations](#49-notebook--cell-operations-fr-nb)
   - 4.10 [Conversational Follow-Up & Cell Edit](#410-conversational-follow-up--cell-edit-fr-conv)
   - 4.11 [Reporting & Export](#411-reporting--export-fr-report)
   - 4.12 [Admin & Audit](#412-admin--audit-fr-admin)
   - 4.13 [Frontend UI](#413-frontend-ui-fr-ui)
   - 4.14 [LLM Integration](#414-llm-integration-fr-llm)
   - 4.15 [Real-Time Progress & WebSocket](#415-real-time-progress--websocket-fr-rt)
5. [Non-Functional Requirements](#5-non-functional-requirements)
   - 5.1 [Security](#51-security-nfr-sec)
   - 5.2 [Performance & Scalability](#52-performance--scalability-nfr-perf)
   - 5.3 [Reliability & Availability](#53-reliability--availability-nfr-rel)
   - 5.4 [Observability](#54-observability-nfr-obs)
   - 5.5 [Accessibility](#55-accessibility-nfr-a11y)
   - 5.6 [Maintainability](#56-maintainability-nfr-maint)
   - 5.7 [Deployability & Operability](#57-deployability--operability-nfr-deploy)
   - 5.8 [Compliance](#58-compliance-nfr-comp)
   - 5.9 [Cost Management](#59-cost-management-nfr-cost)
6. [Data Model & Contracts](#6-data-model--contracts)
7. [Constraints & Assumptions](#7-constraints--assumptions)
8. [Open Questions & Known Gaps](#8-open-questions--known-gaps)
9. [Glossary](#9-glossary)

---

## 1. Document Overview

### 1.1 Purpose

This document is the canonical requirements reference for Inzyts. It records, for every capability of the system:

- **Now** — the as-built behavior in v0.10.0, with file/line refs
- **Target** — the intended behavior per [FUTURE_ROADMAP.md](FUTURE_ROADMAP.md)
- **Gap** — the delta between Now and Target
- **Priority** — P0 (must ship in current/next phase) through P3 (deferred)
- **Acceptance criteria** — testable conditions that confirm the requirement is met

Engineers and AI agents (e.g., Claude Code) maintaining or extending the system should treat this document as the single source of truth when scoping work; if behavior on the ground diverges from this spec, either the code or this spec is wrong — open an issue.

### 1.2 Scope

The full Inzyts product:

- Backend HTTP/WebSocket API (FastAPI + Socket.IO)
- Workflow + 27-agent system + LangGraph orchestration
- LLM integration layer (Anthropic / OpenAI / Gemini / Ollama)
- Frontend SPA (React + TypeScript + Vite)
- Data layer (PostgreSQL + Redis + filesystem + cache)
- Multi-source ingestion (CSV / SQL / cloud storage / REST APIs / cloud DWH)
- Sandbox execution and notebook generation
- Reporting & export (PDF / HTML / PPTX / Markdown)
- Authentication, RBAC, audit logging, rate limiting
- Infrastructure (Docker Compose, Celery, Alembic, CI/CD)
- Test suite (~112 backend test files + Playwright + axe-core frontend tests)

Out of scope: cloud-native K8s deployment, marketplace, third-party plugins (all on roadmap but not yet shipped).

### 1.3 Audience

Primary: **internal engineers** picking up the codebase, and **agentic AI systems** (e.g., Claude Code) maintaining or extending the system. Secondary: external auditors and design partners reviewing the system.

The document is dense and assumes Python + TypeScript + Docker fluency. Domain jargon is defined in §9.

### 1.4 Conventions

- **FR** = Functional Requirement; **NFR** = Non-Functional Requirement
- **ID format:** `<TYPE>-<AREA>-<NNN>` (e.g. `FR-AUTH-001`, `NFR-SEC-003`). IDs are stable; never renumber.
- **Status:** Implemented / Partial / Planned / Deferred
- **Priority:** **P0** (current/next phase, must-have) · **P1** (within 6 months) · **P2** (6–12 months) · **P3** (>12 months / parking)
- **Phase** mapping (per [FUTURE_ROADMAP.md](FUTURE_ROADMAP.md)): **Phase 1 = months 0–3 ("Trust") · Phase 2 = 3–6 ("Sellability") · Phase 3 = 6–12 ("Leverage")**
- **File references:** [path:line](path) markdown links throughout
- A requirement labelled "Implemented · P0" means the current behavior already satisfies the P0 commitment — Gap = None
- A requirement labelled "Partial · P0" means current behavior partially satisfies and the Gap closes the rest

### 1.5 Related Documents

| Document | Role | Relation to this SPEC |
|---|---|---|
| [README.md](../README.md) | User-facing orientation, install, examples | Quick-start; this SPEC is more rigorous |
| [architecture.md](architecture.md) | High-level system architecture | Diagrams + intent; this SPEC adds testable requirements |
| [SECURITY.md](../SECURITY.md) | Operational security controls | Authoritative for current security posture |
| [FUTURE_ROADMAP.md](FUTURE_ROADMAP.md) | 12-month strategic roadmap | Authoritative for "Target" / "Desired behavior" columns |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Contributor workflow | Outside this SPEC's scope |

### 1.6 Change Log

| Version | Date | Author | Change |
|---|---|---|---|
| 0.1.0 | 2026-05-04 | Initial drafting | Initial as-built + target spec for v0.10.0 baseline |

---

## 2. Stakeholders & Personas

### 2.1 Personas

| Persona | Goals | Inzyts touchpoint |
|---|---|---|
| **Data Analyst** | Get to a defensible answer fast; share polished output | Web UI; export to PDF/PPTX; conversational follow-up |
| **Data Scientist / ML Engineer** | Trust ML conclusions; track experiments; reuse profiles | Predictive/Diagnostic/Forecasting modes; cost-per-job; (target) confidence scoring + MLflow |
| **Business User** | Plain-English insights; embedded reports | Executive summary; (target) dashboards + share-by-link |
| **Enterprise Admin** | RBAC, audit trail, compliance, cost control | Admin pages; audit log queries; (target) SSO + per-user budgets |
| **Internal Engineer** | Onboard fast; extend safely | This SPEC; CLAUDE.md; tests |
| **AI Agent (MCP client / Claude Code)** | Programmatic data analysis; maintain Inzyts itself | (target) MCP server; current REST API |

### 2.2 Roles in the Application

Three RBAC tiers, hierarchical: **Admin** > **Analyst** > **Viewer**. Defined in the `users.role` PostgreSQL enum and embedded in JWT claims. Hierarchy enforced by `require_role()` ([src/server/middleware/auth.py](../src/server/middleware/auth.py)). System API tokens (`INZYTS_API_TOKEN`) receive Admin role.

| Role | Capabilities |
|---|---|
| **Viewer** | Read own jobs / notebooks / reports |
| **Analyst** | Viewer + create analysis jobs, upload files, follow-up conversations, cell editing |
| **Admin** | Analyst + user CRUD, audit log queries, cross-user job access |

---

## 3. System Context

### 3.1 Architecture Snapshot (v0.10.0)

```
┌──────────────────────────────────────────────────────────────────────┐
│                         External Boundary                            │
│                                                                      │
│   Browser ── HTTPS ──► Reverse Proxy (production: nginx + TLS)       │
│                                │                                     │
└────────────────────────────────┼─────────────────────────────────────┘
                                 │
                                 ▼
   ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
   │  Frontend SPA    │◄──►│  Backend API     │◄──►│  Celery Worker   │
   │  (React + Vite)  │ WS │  (FastAPI +      │    │  (LangGraph +    │
   │  port 5173       │    │   Socket.IO)     │    │   27 agents)     │
   │                  │    │  port 8000       │    │                  │
   └──────────────────┘    └─────────┬────────┘    └─────────┬────────┘
                                     │                       │
                              ┌──────┼───────────────────────┼───────┐
                              ▼      ▼                       ▼       ▼
                       ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
                       │ PostgreSQL │ │   Redis    │ │ Filesystem │ │ Sandbox    │
                       │  port 5432 │ │  port 6379 │ │ uploads/   │ │ (KernelSbx)│
                       │  (jobs,    │ │ (progress, │ │ output/    │ │  per-job   │
                       │   users,   │ │  rate-lim, │ │ cache/     │ │  process   │
                       │   audit)   │ │  cache)    │ │            │ │  group     │
                       └────────────┘ └────────────┘ └────────────┘ └────────────┘
                                                                          │
                                                                          ▼
                       ┌──────────────────────────────────────────────────────────┐
                       │  External egress (allowlisted via iptables on entrypoint)│
                       │  • LLMs: api.anthropic.com / api.openai.com /            │
                       │           generativelanguage.googleapis.com / Ollama     │
                       │  • Customer DBs: PG/MySQL/MSSQL/BQ/Snowflake/RS/Databricks│
                       │  • Cloud storage: S3 / GCS / Azure Blob                  │
                       │  • REST APIs (with SSRF guard)                           │
                       └──────────────────────────────────────────────────────────┘
```

### 3.2 External Dependencies

| Dependency | Purpose | Failure mode |
|---|---|---|
| LLM provider (Anthropic / OpenAI / Gemini / Ollama) | Code generation, reasoning, narration | Job fails; cached profiles unaffected |
| Customer DB (PG/MySQL/MSSQL/cloud DWH) | SQL ingestion path | Job fails at ingestion node |
| Cloud storage (S3/GCS/Azure) | Cloud ingestion path | Same |
| REST APIs (SSRF-guarded) | API ingestion path | Same |
| PostgreSQL 15 | Persistent storage | App refuses to start; existing jobs preserve state in cache |
| Redis 7 | Real-time progress, rate limit, kernel session registry | Progress events drop; rate limiter fails open or closed depending on slowapi config |
| Browser (Chromium/Firefox/Safari, modern) | Frontend SPA host | N/A — no graceful downgrade for legacy browsers |

### 3.3 Trust Boundaries

1. **User → Frontend**: HTTPS via reverse proxy. Frontend runs in user's browser; treat as untrusted.
2. **Frontend → Backend**: Authenticated via JWT bearer in `Authorization` header (or system API token for server-to-server). Frontend stores JWT in `sessionStorage` only — never `localStorage`, never cookies.
3. **Backend ↔ Postgres / Redis**: Bound to `127.0.0.1` in compose by default. Compose network `db` is internal.
4. **Backend → External LLMs**: Egress to allowlisted hosts only (controlled by `INZYTS_NETWORK_ISOLATION` + iptables in [docker-entrypoint.sh](../docker-entrypoint.sh)).
5. **Worker → Sandbox kernel**: Per-job process group; `setsid()` enforced; stripped env (no API keys); proxy-blackholed; allowlisted imports; 60s wall-clock timeout per cell. Kernel still runs as user `inzyts` inside the container — gVisor / Firecracker upgrade is on the [Phase 3 roadmap](FUTURE_ROADMAP.md#perspective-3--software-architect).

---

## 4. Functional Requirements

> **Format per requirement:** ID + title in bold, status/priority badges, then *Now / Target / Gap / Acceptance* blocks. "None" in Gap means the current behavior already satisfies the target.

### 4.1 Authentication & Authorization (FR-AUTH-*)

#### FR-AUTH-001 · JWT login via password grant — *Implemented · P0*
- **Now:** `POST /api/v2/auth/login` (form-urlencoded) accepts `username` + `password`; verifies bcrypt hash with constant-time comparison ([src/server/middleware/auth.py:29-43](../src/server/middleware/auth.py#L29-L43)); returns `{access_token, token_type:"bearer", role, username}`. JWT `exp` claim set from `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default 7 days; CI uses 240 min).
- **Target:** Add SSO (OIDC + SAML via WorkOS / Authentik) and MFA enforcement.
- **Gap:** No SSO; no MFA. Phase 2 P0.
- **Acceptance:** (i) wrong password yields 401 in constant time vs unknown user; (ii) successful login returns valid JWT; (iii) audit row recorded with IP, username, timestamp; (iv) `/auth/login` rate-limited at 10/min/IP.

#### FR-AUTH-002 · System API token (server-to-server) — *Implemented · P0*
- **Now:** `INZYTS_API_TOKEN` env var; verified in `Authorization: Bearer <token>` header via `secrets.compare_digest`; receives `admin` role automatically ([SECURITY.md](../SECURITY.md)).
- **Target:** Tokens issued via secrets manager (Vault / AWS SM); rotatable; per-token scopes.
- **Gap:** Plaintext in `.env`; no rotation; no scopes. Phase 2 P0 (`NFR-SEC-005`).
- **Acceptance:** (i) request with token succeeds against admin endpoints; (ii) constant-time comparison verified by test.

#### FR-AUTH-003 · First-boot admin auto-creation — *Implemented · P0*
- **Now:** On startup, if no admin exists, server creates one from `ADMIN_USERNAME` (default `admin`) + `ADMIN_PASSWORD` (required). Server refuses to start if `ADMIN_PASSWORD` unset in production.
- **Target:** Same, but credentials read from secrets manager.
- **Gap:** Reads from env. Phase 2 P0.
- **Acceptance:** (i) container with no `ADMIN_PASSWORD` exits non-zero; (ii) first boot creates user with `admin` role.

#### FR-AUTH-004 · Three-tier RBAC — *Implemented · P0*
- **Now:** Roles `admin > analyst > viewer` enforced via `require_role()` dependency factory; admins bypass analyst-level checks.
- **Target:** Same plus per-tenant role hierarchies in workspaces (Phase 2).
- **Gap:** Single-tenant only. Phase 2 P0 (depends on FR-WS-001).
- **Acceptance:** (i) viewer hitting `/analyze` returns 403; (ii) admin hitting analyst-only endpoint succeeds.

#### FR-AUTH-005 · Per-job ownership (object-level authz) — *Implemented · P0*
- **Now:** `resolve_owned_job()` ([src/server/db/queries.py:14](../src/server/db/queries.py#L14)) returns 404 (not 403) on unowned job to prevent ID enumeration. Legacy jobs with `user_id IS NULL` are admin-only. Applied to every `/notebooks/*`, `/reports/*`, `/jobs/*` route and the Socket.IO `join_job` handler.
- **Target:** Replace Python-side checks with PostgreSQL row-level security (defense in depth).
- **Gap:** No RLS. Phase 2 P1 (`NFR-SEC-008`).
- **Acceptance:** (i) user A's request for user B's job returns 404; (ii) admin sees both; (iii) Socket.IO `join_job` rejects unauthorized rooms.

#### FR-AUTH-006 · Login rate limiting — *Implemented · P0*
- **Now:** `slowapi` 10/min/IP on `/auth/login`, backed by Redis. Login attempts (success/fail) recorded in `audit_logs` with IP and username. Constant-time dummy hash on unknown user.
- **Target:** Same — no change.
- **Gap:** None.
- **Acceptance:** (i) 11th login attempt in 1min returns 429; (ii) audit row written for both success and failure.

#### FR-AUTH-007 · `GET /auth/me` — current user — *Implemented · P1*
- **Now:** Returns `{id, username, email, role, is_active}` for the bearer token holder ([src/server/routes/auth.py:111](../src/server/routes/auth.py#L111)).
- **Target:** Same plus team/workspace memberships.
- **Gap:** No workspaces yet. Phase 2 P0.
- **Acceptance:** (i) returns current user; (ii) inactive user → 401.

### 4.2 Analysis Initiation (FR-ANALYSIS-*)

#### FR-ANALYSIS-001 · Mode auto-suggestion — *Implemented · P1*
- **Now:** `POST /api/v2/suggest-mode` ([src/server/routes/analysis.py:54](../src/server/routes/analysis.py#L54)) takes `{question, target_column?}` and returns `{suggested_mode, detection_method, confidence, explanation}` for the seven modes. Rate-limited 30/min/IP.
- **Target:** Same; eventually pre-fill mode from a "describe your dataset in one sentence" interaction (P1, Phase 1).
- **Gap:** No conversational onboarding. Phase 1 P1.
- **Acceptance:** (i) supplying a target column biases toward Predictive; (ii) "find weird stuff" question returns Anomaly (target — see FR-MODE-008); (iii) confidence in [0,1].

#### FR-ANALYSIS-002 · `POST /analyze` — submit analysis job — *Implemented · P0*
- **Now:** Validates ≥1 of `csv_path | db_uri | cloud_uri | api_url`; resolves CSV from DB/cloud if specified; estimates cost; creates `Job` row with `user_id`; enqueues Celery task `execution_task`; returns `{job_id, status:"PENDING", created_at, estimated_cost, message}`. Rate-limited 10/min/IP. Analyst+ only.
- **Target:** Add hard cost-budget enforcement before enqueue; reject if user/team over budget.
- **Gap:** Cost is estimated but not capped. Phase 1 P0 (`NFR-COST-001`).
- **Acceptance:** (i) zero data sources → 422; (ii) analyst can submit; viewer cannot; (iii) job_id is a UUID; (iv) estimated_cost > 0 for non-empty job.

#### FR-ANALYSIS-003 · Multi-file input — *Implemented · P1*
- **Now:** `multi_file_input` field accepts a list of file specs; if length > 1 the workflow runs `data_merger` agent before Phase 1 ([src/agents/phase1/data_merger.py](../src/agents/phase1/data_merger.py)).
- **Target:** Same; stretch goal of intelligent join-key suggestion across multiple sources.
- **Gap:** Auto-join-key heuristic is in place but limited.
- **Acceptance:** (i) two CSVs with shared key produce a merged dataset; (ii) merge report includes row count delta.

#### FR-ANALYSIS-004 · Mode coverage — *Implemented · P0*
- **Now:** Seven modes supported: Exploratory, Predictive, Diagnostic, Comparative, Forecasting, Segmentation, Dimensionality (`AnalysisMode` enum [src/server/models/schemas.py:11](../src/server/models/schemas.py#L11), `PipelineMode` enum [src/models/handoffs/_handoffs.py:39-48](../src/models/handoffs/_handoffs.py#L39-L48); enum value mismatch handled in `_MODE_VALUE_MAP`).
- **Target:** Add Anomaly (8th, P1 Phase 2), NLP/text (9th, P3), Geospatial (parking).
- **Gap:** 8th and 9th modes not yet implemented. See FR-MODE-008/009.
- **Acceptance:** (i) all seven modes route to the correct strategy agent; (ii) invalid mode → 422.

#### FR-ANALYSIS-005 · Exclude columns — *Implemented · P1*
- **Now:** `exclude_columns: List[str]` on `AnalysisRequest`; honored by Profiler.
- **Target:** Per-column allow/deny per DB connection (P2, Phase 3).
- **Gap:** No per-connection ACL. P2.
- **Acceptance:** Excluded column never appears in profile or downstream cells.

### 4.3 Job Management (FR-JOB-*)

#### FR-JOB-001 · `GET /jobs` — paginated list — *Implemented · P1*
- **Now:** Returns user's jobs (admins see all); filters by status, mode, created_at; `skip`/`limit` (max 200). Rate-limited 200/min/IP.
- **Target:** Cursor-based pagination across history endpoints (`NFR-PERF-006`).
- **Gap:** Skip/limit only — costly at scale. Phase 2 P2.
- **Acceptance:** (i) viewer sees only their jobs; (ii) ordering is stable.

#### FR-JOB-002 · `GET /jobs/{id}` — job detail — *Implemented · P0*
- **Now:** Returns status, progress 0–100, last 500 log lines parsed from file, token_usage, cost_estimate, created_at. Ownership enforced. Rate-limited 30/min/IP.
- **Target:** Stream logs via SSE (`FR-RT-002`); structured event log (replayable).
- **Gap:** Log line cap can truncate chatty runs. Phase 1 P0.
- **Acceptance:** (i) status reflects Celery state; (ii) cost matches sum of phase costs.

#### FR-JOB-003 · `GET /jobs/{id}/columns` — locked column profile — *Implemented · P1*
- **Now:** Returns per-column profile (dtype, cardinality_or_range, role, null_count, stats, histogram) sourced from the locked Phase-1 profile cache.
- **Target:** Same; richer histograms when dataset-as-object lands.
- **Gap:** None against current target.
- **Acceptance:** Pre-Phase-1 → 404 (no profile yet); post-lock → 200 with stable schema.

#### FR-JOB-004 · `GET /jobs/{id}/cost` — cost breakdown by phase — *Implemented · P0*
- **Now:** Returns `total_cost_usd` + rows `[{phase_name, cost_usd, prompt_tokens, completion_tokens, is_estimate}]` from `jobs.cost_breakdown` JSON column. Phase buckets: phase1, phase2, extensions ([src/workflow/graph.py:34-66](../src/workflow/graph.py#L34-L66)).
- **Target:** Add running cost during job (`NFR-OBS-006`); per-user/team rolling spend.
- **Gap:** Final-only; no live meter. Phase 1 P0.
- **Acceptance:** (i) sum(rows.cost_usd) == total_cost_usd; (ii) blended_rate uses separate prompt/completion (not average).

#### FR-JOB-005 · `POST /jobs/{id}/cancel` — *Implemented · P1*
- **Now:** Revokes Celery task with `terminate=True` (Unix); fallback strategy on Windows; updates `jobs.status` to `CANCELLED`.
- **Target:** Add SIGTERM/SIGKILL escalation; emit `cancelled` audit row.
- **Gap:** Audit reason field absent. Phase 2 P2.
- **Acceptance:** (i) running job becomes `CANCELLED`; (ii) Celery task is killed within 5s.

### 4.4 File & Data-Source Handling (FR-DATA-*)

#### FR-DATA-001 · Single & batch file upload — *Implemented · P0*
- **Now:** `POST /files/upload` and `/files/upload_batch`; accepts CSV/Parquet/Excel/JSON; max 100MB per file; magic-bytes MIME validation + `werkzeug.utils.secure_filename` + `validate_path_within(_UPLOAD_DIR)`. Filename randomized to UUID. Analyst+ only.
- **Target:** Multi-sheet Excel ingestion picker (P1, quick win); pre-LLM PII masking option.
- **Gap:** First-sheet only; PII masking only at export. Phase 1 P1.
- **Acceptance:** (i) `.exe` file → 415; (ii) traversal `../etc/passwd` → 400; (iii) saved file owner is `inzyts`.

#### FR-DATA-002 · CSV/Parquet/JSON/Excel preview — *Implemented · P1*
- **Now:** `GET /files/preview?path=` returns first 5 rows + column list + total_rows. Path validated to be inside upload dir.
- **Target:** For files >100MB, skip exact count; sample-based estimate.
- **Gap:** Exact count is O(N). Phase 2 P2.
- **Acceptance:** (i) path outside upload → 400; (ii) preview ≤5 rows.

#### FR-DATA-003 · SQL ingestion (explicit `db_query`) — *Implemented · P0*
- **Now:** `ingest_from_sql()` ([src/server/services/data_ingestion.py:20-102](../src/server/services/data_ingestion.py#L20-L102)) validates query via `validate_select_only()` (sqlglot AST; rejects DML even inside CTEs); enforces `SET TRANSACTION READ ONLY` on PG/MySQL; URI scheme allowlist (`postgresql/mysql/mssql/bigquery/snowflake/redshift/databricks+connector`); host blocklist (loopback, link-local, RFC1918, internal docker hostnames); caps at `SQL_MAX_ROWS` (200K) × `SQL_MAX_COLS` (500); writes CSV to `data/uploads/sql_extract_<uuid>.csv`.
- **Target:** Same; add Delta/Iceberg adapters (`FR-DATA-007`); column-level allow/deny per connection (P2).
- **Gap:** Delta/Iceberg unsupported. Phase 2 P1.
- **Acceptance:** (i) `INSERT` → 400; (ii) CTE-embedded `DELETE` → 400; (iii) loopback URI → 400 unless `INZYTS_DB_URI_ALLOW_LOOPBACK=1`; (iv) result truncated at row cap.

#### FR-DATA-004 · SQL ingestion (autonomous SQL agent) — *Implemented · P0*
- **Now:** When `db_uri` is set without `db_query`, the workflow runs `sql_extraction_node` ([src/workflow/graph.py ~L627](../src/workflow/graph.py)) which uses `SQLExtractionAgent` to introspect schema and generate a SELECT query, validated through the same pipeline as FR-DATA-003.
- **Target:** Push LIMIT into prompt + EXPLAIN-then-confirm (P1 Phase 2 per [FUTURE_ROADMAP.md](FUTURE_ROADMAP.md#perspective-6--data-engineer)).
- **Gap:** Agent emits `SELECT *` then truncates — wasteful. Phase 2 P1.
- **Acceptance:** (i) generated query passes `validate_select_only`; (ii) result CSV obeys row/col caps.

#### FR-DATA-005 · Cloud-storage ingestion — *Implemented · P0*
- **Now:** Schemes `s3://`, `gs://`, `az://`, `abfs://`, `abfss://` only ([src/server/services/cloud_ingestion.py](../src/server/services/cloud_ingestion.py)); credentials must come from env (`AWS_ACCESS_KEY_ID`, `GOOGLE_APPLICATION_CREDENTIALS`, `AZURE_STORAGE_CONNECTION_STRING`); size cap `CLOUD_MAX_DOWNLOAD_MB` (500).
- **Target:** Partitioned cloud reads (column projection on Parquet). P3.
- **Gap:** Whole-file reads only. P3.
- **Acceptance:** (i) `http://` URI → 400; (ii) URI with embedded credentials → 400; (iii) >500MB blob → 413.

#### FR-DATA-006 · REST API ingestion — *Implemented · P0*
- **Now:** `_safe_get` ([src/agents/api_agent.py](../src/agents/api_agent.py)) blocks private/reserved IPs (RFC 1918, link-local, multicast); manual redirect loop re-validates SSRF on every `Location` (max 5 hops); scheme allowlist `http/https`; response cap `API_MAX_RESPONSE_SIZE` (100MB); request timeout `API_TIMEOUT` (30s); auth via Bearer/API-key/Basic in headers only — never URI.
- **Target:** Extend SSRF defense to DNS-rebinding (P3).
- **Gap:** No DNS-rebinding mitigation. P3.
- **Acceptance:** (i) `http://localhost/...` → 400; (ii) 302 → private IP → 400 on second hop; (iii) 6th redirect → 400.

#### FR-DATA-007 · Delta / Iceberg ingestion — *Planned · P1*
- **Now:** Unsupported.
- **Target:** `deltalake` + `pyiceberg` adapters in `data_ingestion.py` ([roadmap line 471](FUTURE_ROADMAP.md)).
- **Gap:** Whole feature. Phase 3 P1.
- **Acceptance:** (i) `delta://path/to/table` URI ingests latest version; (ii) Iceberg table with hidden partitions ingests correctly.

#### FR-DATA-008 · Dataset-as-first-class object — *Planned · P0*
- **Now:** Each upload is per-job; CSV is hashed (`csv_hash` column on `jobs`) but not exposed as a reusable artifact.
- **Target:** `datasets` table; dedupe by content hash; library UI; dataset versioning ([roadmap line 470, 661](FUTURE_ROADMAP.md)).
- **Gap:** Whole feature. Phase 1 P0.
- **Acceptance:** (i) re-uploading identical CSV reuses dataset row; (ii) UI shows dataset library.

### 4.5 Workflow Orchestration (FR-WF-*)

#### FR-WF-001 · LangGraph StateGraph wiring — *Implemented · P0*
- **Now:** Graph defined in [src/workflow/graph.py](../src/workflow/graph.py). Node sequence: `initialize` → conditional (`restore_cache` | `sql_extraction` | `api_extraction` | `data_merger` | `create_phase1_handoff`) → `data_profiler` → `profile_codegen` → `profile_validator` → conditional retry/lock → `exploratory_conclusions` → conditional `transition_to_phase2` (skip if Exploratory) → `extension_node` (Forecasting/Comparative/Diagnostic only) → `strategy` → `analysis_codegen` → `analysis_validator` → conditional retry/rollback → `assemble_notebook` → `end`.
- **Target:** Add structured event log replacing ad-hoc Socket.IO emits (`FR-RT-003`); per-agent OpenTelemetry spans (`NFR-OBS-007`).
- **Gap:** Events ephemeral; no persistent replay. Phase 2 P1.
- **Acceptance:** (i) every conditional edge is exercised by at least one integration test; (ii) `assemble_notebook` is the only path to `end` on success.

#### FR-WF-002 · Token attribution per phase — *Implemented · P0*
- **Now:** Every node calls `_attribute_tokens(updates, state, tokens, prompt, completion, phase)` to accumulate into `phase1_*`, `phase2_*`, `extensions_*` buckets that sum to global totals. Delta pattern: `start_tokens = agent.llm_agent.total_tokens` → `agent.process(...)` → diff.
- **Target:** Same; per-agent + per-LLM-call audit log of prompt/response hashes (`NFR-OBS-005`).
- **Gap:** Aggregated, not per-call. Phase 1 P1.
- **Acceptance:** sum(phase buckets) == global totals across all 27 agents in a recorded run.

#### FR-WF-003 · Self-correcting retry loops — *Implemented · P0*
- **Now:** Validators emit `ValidationReport` with `route_to` and `route_reason`; routing in `route_after_profile_validation` and `route_after_analysis_validation` sends back to Profiler / CodeGen / Strategy with feedback. Issue frequency tracker escalates to Orchestrator after repeated identical issues; max iterations bounded.
- **Target:** Add agentic-debugging agent with tool access (P2).
- **Gap:** Validator-only retry; no debug agent. Phase 2 P2.
- **Acceptance:** (i) two consecutive identical issues escalate; (ii) max iterations reached → graceful end with informative error.

#### FR-WF-004 · Profile lock contract — *Implemented · P0*
- **Now:** `ProfileLock` ([src/models/state.py:38-157](../src/models/state.py#L38-L157)) snapshot on Phase 1 success: `LOCKED` state, SHA256 integrity hash, immutable Pydantic tuple types in `ProfileToStrategyHandoff`. Strategy/CodeGen retrieve via `state.profile_lock.get_locked_handoff()`; `ProfileNotLockedException` on missing lock.
- **Target:** Versioned handoff schemas (`v1`, `v2`) for forward compatibility (`FR-WF-006`).
- **Gap:** Single version. Phase 2 P1.
- **Acceptance:** (i) tampered handoff fails `verify_integrity()`; (ii) Phase 2 cannot start without lock.

#### FR-WF-005 · Phase-1 cache (CSV-hash keyed) — *Implemented · P0*
- **Now:** `CacheManager` ([src/utils/cache_manager.py](../src/utils/cache_manager.py)) writes `~/.cache/inzyts/<csv_hash>/metadata.json` (atomic via `.tmp` + rename); 7-day TTL; SHA256 of CSV bytes; on cache hit, `restore_cache_node` skips Phase 1.
- **Target:** Phase-2 result cache keyed by `(profile_hash, mode, question)` — cross-mode upgrade reuse.
- **Gap:** Phase-1 only. Phase 1 P1 (`FR-CACHE-002`).
- **Acceptance:** (i) identical CSV + intent → cache hit < 1s; (ii) modified CSV → fresh Phase 1.

#### FR-WF-006 · Versioned handoff schemas — *Planned · P1*
- **Now:** Single-version Pydantic models throughout `src/models/handoffs/`.
- **Target:** `v1`, `v2`, … schemas with migration adapters; deprecation contract.
- **Gap:** Whole feature. Phase 2 P1.
- **Acceptance:** (i) v1 cache loads under v2 code via adapter; (ii) deprecation warnings emitted.

### 4.6 Agents & Analysis Modes (FR-AGENT-*, FR-MODE-*)

#### FR-AGENT-001 · 27-agent registry with lazy loading — *Implemented · P0*
- **Now:** `AgentFactory` ([src/workflow/agent_factory.py](../src/workflow/agent_factory.py)) registers each of the 27 agents (3 setup + 6 Phase 1 + 3 extensions + 6 strategy + 2 codegen + 2 validator + 2 conversational + 3 integration); singletons; lazy-imported.
- **Target:** Plugin SDK with capability-decl manifests; replace hardcoded registry with discovery (Phase 3 P0).
- **Gap:** All 27 hardcoded in `graph.py`. Phase 3 P1.
- **Acceptance:** (i) every agent reachable from a unit test; (ii) cold-start time stable.

#### FR-MODE-001..007 · Seven analysis modes — *Implemented · P0*
| ID | Mode | Pipeline | Strategy agent | Extension |
|---|---|---|---|---|
| FR-MODE-001 | Exploratory | P1 + Conclusions | — | — |
| FR-MODE-002 | Predictive | P1 + P2 | `StrategyAgent` (default) | — |
| FR-MODE-003 | Diagnostic | P1 + Ext + P2 | `DiagnosticStrategyAgent` | `DiagnosticExtensionAgent` |
| FR-MODE-004 | Comparative | P1 + Ext + P2 | `ComparativeStrategyAgent` | `ComparativeExtensionAgent` |
| FR-MODE-005 | Forecasting | P1 + Ext + P2 | `ForecastingStrategyAgent` | `ForecastingExtensionAgent` |
| FR-MODE-006 | Segmentation | P1 + P2 | `SegmentationStrategyAgent` | — |
| FR-MODE-007 | Dimensionality | P1 + P2 | `DimensionalityStrategyAgent` | — |

- **Acceptance:** (i) each mode produces a notebook with the expected sections; (ii) mode-specific validators apply correct thresholds (Predictive: accuracy ≥0.60 / R² ≥0.50; Segmentation: silhouette ≥ threshold; etc.).

#### FR-MODE-008 · Anomaly detection (8th mode) — *Planned · P1*
- **Target:** IsolationForest + DBSCAN outliers + LLM narration.
- **Gap:** Not implemented. Phase 2 P1.
- **Acceptance:** (i) tabular dataset with seeded outliers detected; (ii) narration explains top-K anomalies.

#### FR-MODE-009 · NLP / text mode (9th) — *Planned · P3*
- **Target:** Embeddings + BERTopic + classifier on free-text columns.
- **Gap:** Not implemented. Phase 3 P1.

#### FR-AGENT-002 · Confidence scoring on conclusions — *Planned · P0*
- **Now:** None.
- **Target:** Self-consistency sampling + agreement score → UI chip (Low/Med/High).
- **Gap:** Whole feature. Phase 1 P0 (UX dependency: `FR-UI-013`).
- **Acceptance:** (i) every conclusion gets a confidence ∈[0,1]; (ii) ≥90% of conclusions display a chip.

#### FR-AGENT-003 · Multi-LLM router with per-task routing — *Planned · P1*
- **Now:** `agent_factory` returns one global LLM via `settings.llm.default_provider`.
- **Target:** Per-task model routing (cheap for routing/extraction; premium for code generation).
- **Gap:** Whole feature. Phase 2 P1.
- **Acceptance:** (i) routing agent uses haiku-tier model; (ii) codegen uses sonnet-tier or higher; (iii) per-call model recorded in audit.

#### FR-AGENT-004 · LLM call audit log — *Planned · P1*
- **Now:** Cost-only tracking.
- **Target:** Hash of prompt + response per call, with retention policy class.
- **Gap:** Whole feature. Phase 1 P1 (`NFR-OBS-005`).
- **Acceptance:** Audit row written for every LLM call with `(agent, model, prompt_hash, response_hash, tokens_in, tokens_out, latency_ms, cost_usd)`.

#### FR-AGENT-005 · LLM output validation layer — *Partial · P0*
- **Now:** Pydantic schemas validate handoff structure; some regex-denylist on agent outputs (in progress).
- **Target:** Mature output validation: schema + denylist (e.g., no `import os`, no `subprocess`) + per-agent capability allowlist.
- **Gap:** Inconsistent denylist coverage. Phase 1 P0.
- **Acceptance:** Adversarial corpus of malicious LLM outputs is blocked; regression suite green in CI.

### 4.7 Sandbox Execution (FR-SBX-*)

#### FR-SBX-001 · KernelSandbox process-group isolation — *Implemented · P0*
- **Now:** Per-cell execution in a child process via `setsid()`, killed via `_killpg(SIGKILL)` on timeout. Three invariants (`pgid != own_pgid`, `pgid == pid`, `setsid() failure is fatal in child`) prevent worker/parent self-kill ([SECURITY.md](../SECURITY.md) "Sandbox `_killpg` Safety Invariants"). RLIMIT_AS (2GB prod / 4GB dev), RLIMIT_CPU (300s/600s), RLIMIT_NPROC (64/128), RLIMIT_NOFILE (256), RLIMIT_FSIZE (100MB), wall-clock 60s/cell.
- **Target:** Upgrade to gVisor or Firecracker microvm for container-grade isolation (`NFR-SEC-010`).
- **Gap:** Process-group only; LLM-generated code can still target host syscalls. Phase 3 P1.
- **Acceptance:** (i) `import os; os.system("rm -rf /")` killed without affecting worker; (ii) `_killpg` invariants verified by tests in `tests/unit/services/test_sandbox_security.py` (gated `slow`).

#### FR-SBX-002 · Network egress blocking from kernel — *Implemented · P0*
- **Now:** Kernel-subprocess proxy env vars set to `http://127.0.0.1:1` (unroutable blackhole). Container-level iptables OUTPUT allowlist via `docker-entrypoint.sh` (allows DNS, loopback, established, LLM hosts, db/redis only).
- **Target:** Per-UID iptables rules so kernel runs as non-app user, completely blocked.
- **Gap:** Kernel inherits container's allowlist (could exfil to allowlisted LLM URL). Phase 3 P2.
- **Acceptance:** (i) `requests.get('https://example.com')` from kernel times out; (ii) attempt to reach `api.anthropic.com` from kernel succeeds (caveat above).

#### FR-SBX-003 · Allowlisted imports — *Implemented · P0*
- **Now:** Kernel preamble restricts `__import__` to a whitelist (pandas, numpy, sklearn, matplotlib, seaborn, etc.). Adversarial CI test gated `slow`.
- **Target:** Add CI test ungated (P0 Phase 1) so escapes break the build.
- **Gap:** Test exists but skipped by default. Phase 1 P0.
- **Acceptance:** `import socket` in kernel raises `ImportError`.

#### FR-SBX-004 · Secret stripping — *Implemented · P0*
- **Now:** `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc. removed from kernel env before exec.
- **Target:** Same.
- **Gap:** None.
- **Acceptance:** `os.environ.get("ANTHROPIC_API_KEY")` in kernel returns `None`.

#### FR-SBX-005 · Kernel env injection (no os.environ mutation) — *Implemented · P0*
- **Now:** Per-job dataset paths passed to kernel via `extra_env` argument on `KernelSandbox`/`SandboxExecutor`, not via mutating worker `os.environ` ([SECURITY.md](../SECURITY.md) "Kernel Bootstrap Security"). Filename-injection-safe.
- **Target:** Same.
- **Gap:** None.
- **Acceptance:** Crafted filename `'; rm -rf /` reaches kernel as a literal env value, not interpolated into shell.

#### FR-SBX-006 · Cell execution audit — *Implemented · P0*
- **Now:** Every kernel cell execution writes `cell_execution_audit` row (job_id, user_id, code_hash, code_length, duration_ms, success, error_name, killed_reason, policy_name) — migration `d2e3f4a5b6c7`.
- **Target:** Same; surface in admin UI.
- **Gap:** No admin viewer yet.
- **Acceptance:** Row written for every `cells/execute` call.

### 4.8 Profile Lock & Cache (FR-CACHE-*)

#### FR-CACHE-001 · Phase-1 profile cache (file + DB-backed) — *Implemented · P0*
- See FR-WF-005.
- **Acceptance:** identical CSV → cache hit; expired → cache miss.

#### FR-CACHE-002 · Phase-2 result cache — *Planned · P1*
- **Now:** None.
- **Target:** Cache keyed by `(profile_hash, mode, question)`.
- **Gap:** Whole feature. Phase 1 P1.
- **Acceptance:** Same `(profile_hash, mode, question)` returns cached notebook within 1s.

#### FR-CACHE-003 · Cache freshness on upstream drift — *Planned · P1*
- **Target:** Hash-poll upstream (DB / cloud) and invalidate cache on detected drift.
- **Gap:** Cache assumes static inputs. Phase 2 P1.

### 4.9 Notebook & Cell Operations (FR-NB-*)

#### FR-NB-001 · `GET /notebooks/{id}/html` — render notebook as HTML — *Implemented · P0*
- **Now:** Loads `.ipynb`; converts via `nbconvert` (`classic` template); ownership enforced.
- **Target:** Configurable template (`classic` vs `lab`); dark-mode rendering aligned with Ink Black palette.
- **Gap:** Single template. Phase 2 P2.
- **Acceptance:** Cells render in chronological order with outputs.

#### FR-NB-002 · `GET /notebooks/{id}/download` — *Implemented · P1*
- **Now:** Returns `.ipynb` file as `FileResponse`.
- **Target:** Same; add Python-script export (P1 Phase 1).
- **Gap:** Script export missing. Phase 1 P1 (FR-REPORT-005).
- **Acceptance:** Download is valid Jupyter notebook.

#### FR-NB-003 · `GET /notebooks/{id}/cells` — structured JSON cells — *Implemented · P0*
- **Now:** Parses `.ipynb` into JSON list `[{cell_type, source, outputs, ...}]`.
- **Acceptance:** Returns same cell count as `nbformat.read`.

#### FR-NB-003b · `PUT /notebooks/{id}/cells` — persist edited cells back to disk — *Implemented · P1*
- **Now:** Accepts `{cells: [{cell_type, source}, ...]}`; rewrites the on-disk `.ipynb` via `nbformat.v4.new_code_cell` / `new_markdown_cell`; preserves nbformat metadata (kernelspec, language info). Rejects cell types other than `code`/`markdown` with 422. Path validation via `_validate_notebook_path` blocks writes outside `_OUTPUT_DIR`.
- **Target:** Per-cell version history; conflict detection if the file changed since the user loaded it.
- **Gap:** Last-write-wins; no version history. P3.
- **Acceptance:** (i) round-trip — cells written via PUT match those read via GET; (ii) save-then-export reflects edits in PDF/HTML/PPTX; (iii) path-traversal payloads rejected.

#### FR-NB-004 · `POST /notebooks/{id}/cells/execute` — live cell execution — *Implemented · P0*
- **Now:** Runs code in persistent kernel session; streams output via Socket.IO `cell_status`/`cell_output`/`cell_complete`; returns `{execution_id, success, error_name, error_value, duration_ms, execution_count}`. Sandbox enforced.
- **Target:** Add SSE alternative for cells without WebSocket support.
- **Gap:** WebSocket only. Phase 1 P1.
- **Acceptance:** (i) syntax error returns success=false with traceback truncated to MAX_TRACEBACK_LEN; (ii) timeout kills cell within 60s.

#### FR-NB-005 · Kernel restart & interrupt — *Implemented · P0*
- **Now:** `POST /cells/restart` resets kernel state; `POST /cells/interrupt` sends soft interrupt; SandboxPolicy wall-clock enforces hard kill.
- **Acceptance:** Long-running infinite loop interrupted within 60s.

#### FR-NB-006 · Persistent kernel session registry — *Implemented · P0*
- **Now:** Kernel sessions tracked in Redis-backed registry; LRU eviction when session limit reached (graceful degradation).
- **Target:** Warm-pool of pre-spun kernels (P3).
- **Gap:** Cold-start per session. Phase 3 P3.

### 4.10 Conversational Follow-Up & Cell Edit (FR-CONV-*)

#### FR-CONV-001 · `POST /notebooks/{id}/ask` — follow-up Q&A — *Implemented · P1*
- **Now:** Loads conversation history from `conversation_messages`; calls `FollowUpAgent`; agent reads notebook + locked profile + final metrics; generates new code/markdown cells; executes them in the same kernel session; persists user + assistant messages with attached cells.
- **Target:** RAG over past runs (cross-run memory) — "we've analyzed this before, here's what changed" (P1, Phase 3).
- **Gap:** Single-run context. Phase 3 P1.
- **Acceptance:** (i) follow-up generates ≥1 cell; (ii) conversation persists across server restarts.

#### FR-CONV-002 · `GET /notebooks/{id}/conversation` — *Implemented · P1*
- **Now:** Returns chronological messages with attached cells.
- **Acceptance:** Order matches `created_at`.

#### FR-CONV-003 · `POST /notebooks/{id}/cells/edit` — natural-language cell edit — *Implemented · P1*
- **Now:** `CellEditAgent` modifies cell code from instruction; re-executes in kernel; returns `{new_code, output, images, success, error}`. The Notebook tab persists tweaked cells when the user clicks **Save** (FR-NB-003b).
- **Target:** Per-cell version history (P3).
- **Gap:** No history. P3.
- **Acceptance:** "Make this a pie chart" mutates a bar chart and re-renders.

### 4.11 Reporting & Export (FR-REPORT-*)

#### FR-REPORT-001 · Multi-format report export — *Implemented · P0*
- **Now:** `GET|POST /reports/{id}/export?format=` produces PDF (WeasyPrint), HTML (Jinja2 with Inzyts branding), PPTX (python-pptx), Markdown. Optional `include_executive_summary`, `include_pii_masking`. File written to `output/reports/`.
- **Target:** Add Word (.docx) export (P1 quick win); Notebook → Python-script export (P1 quick win).
- **Gap:** Two formats missing. Phase 1 P1.
- **Acceptance:** (i) PDF renders embedded charts; (ii) PPTX deck has title + summary + per-section + appendix slides.

#### FR-REPORT-002 · LLM-generated executive summary — *Implemented · P1*
- **Now:** `GET /reports/{id}/executive-summary` returns `{key_findings, data_quality_highlights, recommendations, summary_text, generated_by}`. Auto-fallback to notebook extraction when LLM unavailable. Backfills on demand for jobs pre-dating the feature.
- **Target:** Same.
- **Gap:** None.
- **Acceptance:** Summary present on every completed job.

#### FR-REPORT-003 · PII detection (regex-based) — *Implemented · P0*
- **Now:** `PIIDetector` ([src/services/pii_detector.py](../src/services/pii_detector.py)) scans markdown + code source + outputs for: email (medium), phone (medium), SSN (high), credit card (high), IPv4 (low, with private/loopback exclusion). Findings deduplicated; partial masking (`j***@example.com`).
- **Target:** Pre-LLM PII masking via Presidio / spaCy NER (opt-in per column); GDPR DSAR endpoints (`FR-ADMIN-005`).
- **Gap:** Detection only post-generation; no NER. Phase 1 P1.
- **Acceptance:** Crafted notebook with seeded SSN → finding with severity high.

#### FR-REPORT-004 · PII masking on export — *Implemented · P1*
- **Now:** `include_pii_masking=true` replaces detected values with placeholders (`[EMAIL]`, `[SSN]`, …) before render.
- **Acceptance:** Exported PDF contains `[EMAIL]`, not the email.

#### FR-REPORT-005 · Word (.docx) + Python-script export — *Planned · P1*
- **Target:** Both formats from same report endpoint.
- **Gap:** Whole feature. Phase 1 P1.

#### FR-REPORT-006 · Webhook notifications — *Planned · P1*
- **Target:** Job-lifecycle webhooks (started / completed / failed) → Slack / Teams / generic HTTP.
- **Gap:** Whole feature. Phase 1 P1.
- **Acceptance:** Configured webhook receives job-completed payload within 5s of `assemble_notebook`.

### 4.12 Admin & Audit (FR-ADMIN-*)

#### FR-ADMIN-001 · User CRUD — *Implemented · P0*
- **Now:** `GET|POST|PUT|DELETE /admin/users[/{id}]`. Admin-only; rate-limited 200/min/IP. Username uniqueness; password ≥6 chars; cannot self-delete.
- **Target:** Bulk operations; per-team admin scope.
- **Gap:** Single-tenant; no bulk. Phase 2 P2.
- **Acceptance:** (i) viewer hitting `/admin/users` → 403; (ii) admin self-delete → 400.

#### FR-ADMIN-002 · Audit log query — *Implemented · P0*
- **Now:** `GET /admin/audit-logs?username=&action=&since=&until=` with filters; `GET /admin/audit-logs/summary` returns counts grouped by action.
- **Target:** Cursor pagination; export to CSV.
- **Gap:** Skip/limit only. Phase 2 P2.
- **Acceptance:** Audit row recorded for every user-management mutation.

#### FR-ADMIN-003 · Audit middleware — *Implemented · P0*
- **Now:** `AuditMiddleware` ([src/server/middleware/audit.py](../src/server/middleware/audit.py)) auto-records requests to audited prefixes (`/auth/`, `/analyze`, `/files/`, `/jobs/`, `/admin/`). `record_audit()` async helper for fine-grained logging. Audit failures never break the request flow. IP from `X-Forwarded-For` only when source is trusted proxy.
- **Target:** Add LLM prompt/response hash logging (`NFR-OBS-005`).
- **Gap:** No LLM-call audit. Phase 1 P1.
- **Acceptance:** Authn success/failure + analyze + upload + cancel all produce audit rows.

#### FR-ADMIN-004 · Templates management — *Implemented · P2*
- **Now:** `GET|POST /templates`, `DELETE /templates/{domainName}`. YAML domain templates for analysis presets.
- **Target:** Plugin-marketplace browse/install/submit (P3).
- **Gap:** Local-only. Phase 3 P2.

#### FR-ADMIN-005 · GDPR DSAR endpoints — *Planned · P1*
- **Target:** `DELETE /admin/dsar/users/{username}` (cascade) + `GET /admin/dsar/export/{username}` (export user data zip).
- **Gap:** Whole feature. Phase 2 P1.
- **Acceptance:** DSAR delete removes user + jobs + notebooks + audit + cache rows.

### 4.13 Frontend UI (FR-UI-*)

#### FR-UI-001 · Routes — *Implemented · P0*
| Path | Component | Auth |
|---|---|---|
| `/login` | [LoginPage.tsx](../frontend/src/pages/LoginPage.tsx) | Public |
| `/` | [NewAnalysisPage.tsx](../frontend/src/pages/NewAnalysisPage.tsx) | Analyst+ |
| `/jobs/:jobId` | [JobDetailsPage.tsx](../frontend/src/pages/JobDetailsPage.tsx) | Analyst+ |
| `/templates` | [TemplatesPage.tsx](../frontend/src/pages/TemplatesPage.tsx) | Analyst+ |
| `/admin/users` | [AdminUsersPage.tsx](../frontend/src/pages/AdminUsersPage.tsx) | Admin |
| `/admin/audit` | [AdminAuditPage.tsx](../frontend/src/pages/AdminAuditPage.tsx) | Admin |

- **Acceptance:** Direct nav to admin route as analyst → redirect to `/`.

#### FR-UI-002 · Analysis form (multi-source) — *Implemented · P0*
- **Now:** [AnalysisForm.tsx](../frontend/src/components/AnalysisForm.tsx) with tabs: Upload Files, Manual Path, SQL Database, Cloud Storage, REST API. DB connection test + SQL preview + API preview. Mode picker + question + target column + exclude columns + cache toggle.
- **Target:** Demo dataset gallery + 30s onboarding tour (P1 quick win); Cmd-K command palette.
- **Gap:** No demo gallery; no palette. Phase 1 P1.
- **Acceptance:** Submit creates job and navigates to `/jobs/:id`.

#### FR-UI-003 · Mode suggestion (debounced) — *Implemented · P1*
- **Now:** `useModeSuggestion` debounces calls to `/suggest-mode`; renders `{suggested_mode, confidence, explanation}` with one-click apply.
- **Acceptance:** Typing-debounced; only fires after 500ms idle.

#### FR-UI-004 · CommandCenter view (6 tabs) — *Implemented · P0*
- **Now:** [CommandCenterView.tsx](../frontend/src/components/command-center/CommandCenterView.tsx) — Overview, Visual, Code, Data, Logs, Events. Keyboard shortcuts: `1–6` switch tabs; `Esc` deselect; `Cmd/Ctrl+Enter` re-run.
- **Target:** Add Cost meter live during run (P0); Confidence chip on conclusions (P0).
- **Gap:** Cost final-only; no chip. Phase 1 P0.
- **Acceptance:** All 6 tabs render without console errors.

#### FR-UI-005 · Phase progress bar — *Implemented · P0*
- **Now:** [PhaseBlock.tsx](../frontend/src/components/command-center/PhaseBlock.tsx) renders Phase 1 / Extensions / Phase 2 with elapsed + ETA, fed by Socket.IO `phase_update`.
- **Acceptance:** Bar advances during run; reaches 100% on completion.

#### FR-UI-006 · Live notebook panel (cell streaming) — *Implemented · P0*
- **Now:** `LivePanel` consumes `cell_status` / `cell_output` / `cell_complete` Socket.IO events; renders text / error / HTML (DOMPurify-sanitized) / images.
- **Acceptance:** Output appears within 200ms of kernel emission.

#### FR-UI-007 · Interactive cell edit (NL instruction) — *Implemented · P1*
- **Now:** [InteractiveCell.tsx](../frontend/src/components/InteractiveCell.tsx) → `POST /cells/edit` → re-render with new output + images.
- **Acceptance:** "Add error bars" produces visibly different chart.

#### FR-UI-008 · Conversational follow-up chat — *Implemented · P1*
- **Now:** [FollowUpChat.tsx](../frontend/src/components/FollowUpChat.tsx) loads history, submits questions, auto-scrolls, renders markdown via DOMPurify.
- **Acceptance:** Q&A persists across page reload.

#### FR-UI-009 · Report export menu — *Implemented · P0*
- **Now:** [NotebookViewer.tsx](../frontend/src/components/NotebookViewer.tsx) menu offers PDF / HTML / PPTX / Markdown; downloads as Blob.
- **Target:** Add Word + Python-script (FR-REPORT-005); persistent Export button on every completed job.
- **Gap:** Two formats missing; export discoverability suboptimal. Phase 1 P1.
- **Acceptance:** Each format downloads a file.

#### FR-UI-010 · Admin pages — *Implemented · P1*
- **Now:** [AdminUsersPage.tsx](../frontend/src/pages/AdminUsersPage.tsx) and [AdminAuditPage.tsx](../frontend/src/pages/AdminAuditPage.tsx).
- **Acceptance:** Non-admin → redirect.

#### FR-UI-011 · JobContext state management — *Implemented · P0*
- **Now:** React Context ([JobContext.tsx](../frontend/src/context/JobContext.tsx)) holds jobs, activeJobId, logs, events, progress, metrics, phases, isConnected, toasts.
- **Acceptance:** Switching active job rejoins Socket.IO room.

#### FR-UI-012 · DOMPurify markdown sanitization — *Implemented · P0*
- **Now:** Strict tag/attribute allowlist (h1–h6, strong, em, code, pre, br, p, ul, ol, li, a, blockquote, table). DB URI scheme allowlist on form input; file path inputs reject colon characters.
- **Acceptance:** `<script>alert(1)</script>` in markdown does not execute.

#### FR-UI-013 · Confidence chip on conclusions — *Planned · P0*
- **Target:** Low/Med/High pill on every conclusion card with tooltip.
- **Gap:** Whole feature. Phase 1 P0.

#### FR-UI-014 · Real-time cost meter — *Planned · P0*
- **Target:** Live cost meter during run + budget bar per user.
- **Gap:** Whole feature. Phase 1 P0.

#### FR-UI-015 · Cmd-K command palette — *Planned · P1*
- **Target:** Jump to job, re-run, ask follow-up, switch mode.
- **Gap:** Whole feature. Phase 1 P1.

#### FR-UI-016 · Demo dataset gallery + onboarding — *Planned · P1*
- **Target:** Sample datasets + 30s tour for first-run users.
- **Gap:** Whole feature. Phase 1 P1.

#### FR-UI-017 · Dashboard builder (pinned cells) — *Planned · P0*
- **Target:** Pin cells from notebook → widget-based dashboards. Explicit non-goal: don't try to be Tableau.
- **Gap:** Whole feature. Phase 2 P0.

#### FR-UI-018 · Mobile read-only view — *Planned · P2*
- **Target:** Read-only view (history + share links + report download) on tablets/phones.
- **Gap:** Whole feature. Phase 2 P2.

### 4.14 LLM Integration (FR-LLM-*)

#### FR-LLM-001 · Multi-provider support — *Implemented · P0*
- **Now:** `get_llm()` factory ([src/llm/provider.py](../src/llm/provider.py)) returns `BaseChatModel` for Anthropic / OpenAI / Gemini / Ollama; default per `settings.llm.default_provider`. Lazy init for Ollama (local-only mode).
- **Acceptance:** Switching `INZYTS__LLM__DEFAULT_PROVIDER` swaps provider on next job.

#### FR-LLM-002 · LLMAgent token tracking + retry — *Implemented · P0*
- **Now:** Wraps any chat model with prompt/completion/total token tracking via `usage_metadata` (4-char-per-token estimation fallback); 5 retries with exponential backoff on connection errors; structured prompt (system + user); JSON-extraction helper.
- **Acceptance:** (i) total tokens ≥0 on every call; (ii) 5 transient failures retry; 6th propagates.

#### FR-LLM-003 · MCP server (expose Inzyts as MCP tool) — *Planned · P0*
- **Target:** Expose `analyze`, `follow-up`, `reports` as MCP tools so Claude Desktop / Cursor / Cline can drive Inzyts.
- **Gap:** Whole feature. Phase 1 P0.
- **Acceptance:** MCP-connected client can submit a job and retrieve the report.

### 4.15 Real-Time Progress & WebSocket (FR-RT-*)

#### FR-RT-001 · Socket.IO progress + log channel — *Implemented · P0*
- **Now:** Auth via Bearer token at handshake; `join_job` validates ownership; emits `log`, `progress`, `phase_update`, `metrics_snapshot`, `cell_status`, `cell_output`, `cell_complete`, `agent_event` to per-job rooms. Server-side credential scrubbing on `log` events (DB URIs, API keys masked).
- **Target:** Add SSE alternative (`FR-RT-002`); persistent event log (`FR-RT-003`).
- **Gap:** WebSocket only; ephemeral. Phase 1 P0.
- **Acceptance:** Disconnect → reconnect resubscribes to same room.

#### FR-RT-002 · SSE-streamed agent reasoning — *Planned · P0*
- **Target:** Token-by-token agent thoughts via Server-Sent Events; collapsible thought panel in UI.
- **Gap:** Whole feature. Phase 1 P0.
- **Acceptance:** Median perceived time-to-first-output < 30s.

#### FR-RT-003 · Persistent structured event log — *Planned · P1*
- **Target:** All progress/agent events written to a `job_events` table (or kafka-style log) with tail API for replay.
- **Gap:** Whole feature. Phase 2 P1.
- **Acceptance:** Replay any past job's events end-to-end.

---

## 5. Non-Functional Requirements

### 5.1 Security (NFR-SEC-*)

#### NFR-SEC-001 · Bcrypt password hashing — *Implemented · P0*
- **Now:** `passlib[bcrypt]` cost 12; constant-time verification; dummy hash for unknown user.
- **Acceptance:** Login response time invariant to user existence within ±10ms.

#### NFR-SEC-002 · TLS termination — *Partial · P1*
- **Now:** No built-in TLS — relies on operator's reverse proxy. README recommends nginx + TLS for public deployments.
- **Target:** TLS 1.3 enforcement; HSTS; cert auto-rotation guidance.
- **Gap:** No enforcement. Phase 2 P1.

#### NFR-SEC-003 · CORS allowlist — *Implemented · P0*
- **Now:** `allowed_origins` configurable; defaults `http://localhost:5173`, `http://localhost:8000`, `http://127.0.0.1:5173`. credentials: true. Methods: GET/POST/PUT/DELETE/OPTIONS.
- **Acceptance:** Cross-origin from non-allowed origin → blocked at preflight.

#### NFR-SEC-004 · Rate limiting (slowapi) — *Implemented · P0*
- **Now:** Redis-backed; default 200/min/IP; per-route overrides (login 10/min, analyze 10/min, suggest-mode 30/min, jobs detail 30/min).
- **Target:** Tiered limits per role/tier (Pro 100/min; Team 1000/min) — Phase 2 P1.

#### NFR-SEC-005 · Secrets manager — *Planned · P0*
- **Target:** Replace `.env` with Vault / AWS Secrets Manager adapter. JWT secret, LLM keys, admin password rotated.
- **Gap:** Whole feature. Phase 2 P0.

#### NFR-SEC-006 · SAST + dep-scan in CI — *Planned · P0*
- **Target:** Semgrep + `pip-audit` + `npm audit` + container scan (Trivy/Snyk) on every PR.
- **Gap:** None of these in CI today. Phase 1 P0.
- **Acceptance:** PR with known-vulnerable dep blocked at CI.

#### NFR-SEC-007 · DAST on staging — *Planned · P1*
- **Target:** OWASP ZAP weekly scan against staging.
- **Gap:** Whole feature. Phase 2 P1.

#### NFR-SEC-008 · PostgreSQL row-level security — *Planned · P1*
- **Target:** RLS on `jobs`, `notebooks`, `datasets` (when datasets land), `conversation_messages`.
- **Gap:** Python-side checks only. Phase 2 P1.
- **Acceptance:** Direct DB query as user A returns 0 rows for user B's jobs.

#### NFR-SEC-009 · Per-tenant envelope encryption — *Planned · P1*
- **Target:** Per-tenant keys for upload/output files.
- **Gap:** Whole feature. Phase 2 P1.

#### NFR-SEC-010 · Sandbox upgrade (gVisor / Firecracker) — *Planned · P2*
- See FR-SBX-001.
- **Gap:** Phase 3 P1.

#### NFR-SEC-011 · Prompt-injection regression corpus — *Partial · P0*
- **Now:** [tests/safety/test_prompt_injection.py](../tests/safety/test_prompt_injection.py) exists with seed corpus.
- **Target:** Expand corpus on each new injection technique surfaced; gate CI on green.
- **Gap:** Limited corpus. Phase 1 P0.

#### NFR-SEC-012 · Sandbox-escape adversarial CI test — *Partial · P0*
- **Now:** Real-kernel tests exist behind `slow` marker; skipped by default.
- **Target:** Ungate (or run nightly) so escapes fail CI.
- **Gap:** Skipped. Phase 1 P0.

#### NFR-SEC-013 · Threat-model section in PR template — *Planned · P1*
- **Target:** STRIDE prompts in `.github/pull_request_template.md`.
- **Gap:** Whole feature. Phase 1 P1.

### 5.2 Performance & Scalability (NFR-PERF-*)

#### NFR-PERF-001 · Phase-1 cache hit latency — *Implemented · P0*
- **Target:** < 1s from request to "skip Phase 1" decision.
- **Acceptance:** p95 ≤ 1s in benchmark.

#### NFR-PERF-002 · Sample large datasets — *Implemented · P1*
- **Now:** `agent.max_rows_to_sample = 10,000` for >100K-row datasets ([src/config](../src/config/__init__.py)).
- **Target:** Adaptive stratified sampling per mode (P2).
- **Gap:** Fixed sample. Phase 2 P2.

#### NFR-PERF-003 · Cell timeout — *Implemented · P0*
- **Now:** 60s wall-clock per cell (prod); 300s (dev).
- **Acceptance:** Cell exceeding 60s → killed via `_killpg`.

#### NFR-PERF-004 · Worker autoscaling — *Planned · P2*
- **Now:** Static Celery concurrency.
- **Target:** KEDA-driven autoscaling on queue depth.
- **Gap:** Whole feature. Phase 2 P2.

#### NFR-PERF-005 · Connection pooling — *Implemented · P1*
- **Now:** SQLAlchemy async engine with `db.max_retries=15` and `db.retry_interval=2`.
- **Target:** PgBouncer + read replicas (P2).
- **Gap:** Single instance. Phase 2 P2.

#### NFR-PERF-006 · Cursor-based pagination — *Planned · P2*
- **Now:** `skip`/`limit` across `/jobs`, `/admin/audit-logs`, `/admin/users`.
- **Target:** Cursor-based for stable ordering at scale.
- **Gap:** Phase 2 P2.

#### NFR-PERF-007 · Frontend bundle size — *Implemented · P1*
- **Target:** First contentful paint <2s on typical broadband.
- **Acceptance:** Vite production build ≤500 KB gzipped.

### 5.3 Reliability & Availability (NFR-REL-*)

#### NFR-REL-001 · Service healthchecks — *Implemented · P0*
- **Now:** Backend: `curl -f http://localhost:8000/health` (15s/3 retries/30s start). Postgres: `pg_isready` (5s/10 retries). Redis: `redis-cli ping` (5s/5 retries). Frontend depends on backend health.
- **Acceptance:** Healthcheck failure → restart policy `on-failure:5`.

#### NFR-REL-002 · Audit-failure tolerance — *Implemented · P0*
- **Now:** Audit middleware exceptions logged but never break the request.
- **Acceptance:** Audit DB outage → requests still succeed.

#### NFR-REL-003 · Database migration on startup — *Implemented · P0*
- **Now:** `docker-entrypoint.sh` runs `alembic upgrade head` before backend health passes.
- **Acceptance:** Fresh DB → schema present after first startup.

#### NFR-REL-004 · Restart policy — *Implemented · P0*
- **Now:** `on-failure:5` for db / redis / backend / worker (prevents infinite restart).
- **Acceptance:** 6th consecutive failure stops restart.

#### NFR-REL-005 · Daily backups + PITR — *Planned · P2*
- **Target:** Automated PG backups + point-in-time recovery.
- **Gap:** Whole feature. Phase 2 P2.

### 5.4 Observability (NFR-OBS-*)

#### NFR-OBS-001 · Structured logging — *Implemented · P0*
- **Now:** [src/utils/logger.py](../src/utils/logger.py) with `LogEvents` enum (60+ types: MODE_DETECTED, CACHE_*, PHASE1/2_*, AGENT_*, VALIDATION_*, …); RotatingFileHandler 10 MB × 5 backups; console at WARNING+.
- **Target:** Centralized log aggregation (Loki / ELK).
- **Gap:** Docker logs only. Phase 2 P1.

#### NFR-OBS-002 · Phase progress tracker (Redis + DB) — *Implemented · P0*
- **Now:** Dual-write: Redis `job_progress:<job_id>` (24h TTL) + SQL `job_progress` row (persistent audit). Event-to-percentage map in [src/server/services/progress_tracker.py](../src/server/services/progress_tracker.py).
- **Acceptance:** Frontend progress bar reaches 100% on success.

#### NFR-OBS-003 · Cost tracking per job — *Implemented · P0*
- **Now:** [src/server/services/cost_estimator.py](../src/server/services/cost_estimator.py) with per-model pricing table (Anthropic, OpenAI, Gemini, Ollama=0); separate prompt/completion rate.
- **Target:** Per-user/team rolling spend (`NFR-COST-001`).
- **Gap:** Per-job only. Phase 1 P0.

#### NFR-OBS-004 · Audit logging — *Implemented · P0*
- See FR-ADMIN-003.

#### NFR-OBS-005 · LLM call audit — *Planned · P1*
- See FR-AGENT-004.

#### NFR-OBS-006 · OpenTelemetry tracing — *Planned · P1*
- **Target:** Per-agent spans → Tempo / Jaeger.
- **Gap:** Whole feature. Phase 2 P1.

#### NFR-OBS-007 · Centralized SIEM — *Planned · P1*
- **Target:** Loki + Grafana (or Datadog) with alert rules + IR playbooks.
- **Gap:** Whole feature. Phase 2 P1.

#### NFR-OBS-008 · Prometheus + Grafana metrics — *Planned · P2*
- **Target:** App + DB + worker metrics with AlertManager.
- **Gap:** Whole feature. Phase 2 P2.

### 5.5 Accessibility (NFR-A11Y-*)

#### NFR-A11Y-001 · WCAG 2.1 AA compliance — *Partial · P1*
- **Now:** [frontend/tests/a11y/wcag.spec.ts](../frontend/tests/a11y/wcag.spec.ts) runs axe-core on login + (optionally) authenticated pages; serious/critical violations fail the build.
- **Target:** Full audit; color contrast on Ink Black palette (some text <4.5:1); ARIA labels on charts; screen reader chart alt-text via LLM-generated captions; reduced-motion respect.
- **Gap:** Audit incomplete. Phase 2 P2.

#### NFR-A11Y-002 · Keyboard navigation — *Partial · P1*
- **Now:** Focus ring (2px turquoise); tab order; shortcuts (1–6, Esc, Cmd/Ctrl+Enter).
- **Target:** Standardize Radix focus management; cmd-K palette (FR-UI-015).
- **Gap:** Modal focus traps inconsistent. Phase 2 P2.

#### NFR-A11Y-003 · Screen-reader chart alt-text — *Planned · P2*
- **Target:** LLM-generated alt-text per chart embedded in ARIA labels.
- **Gap:** Whole feature. Phase 2 P2.

#### NFR-A11Y-004 · `prefers-reduced-motion` — *Planned · P2*
- **Target:** Respect globally.
- **Gap:** Animations not reducible. Phase 2 P2.

### 5.6 Maintainability (NFR-MAINT-*)

#### NFR-MAINT-001 · Test suite — *Implemented · P0*
- **Now:** 112 backend test files (85 unit / 20 integration / 2 security / 1 safety / 1 performance / 1 contracts / 1 ui / 1 e2e); pytest markers `requires_redis`, `requires_db`, `slow`. Frontend: 1 e2e (`critical-journey.spec.ts`) + 1 a11y (`wcag.spec.ts`); Vitest configured but no unit tests yet.
- **Target:** Frontend unit tests (`@testing-library/react` is installed but unused).
- **Gap:** Frontend unit coverage near zero. Phase 2 P1.

#### NFR-MAINT-002 · Type safety — *Implemented · P0*
- **Now:** Backend: Pydantic v2 throughout; mypy configured (loose: `ignore_missing_imports=true`). Frontend: TypeScript strict mode; ESLint `@typescript-eslint`.
- **Target:** Tighten mypy; mutation testing on more modules.
- **Gap:** Lax mypy. Phase 2 P3.

#### NFR-MAINT-003 · Mutation testing — *Partial · P2*
- **Now:** mutmut config in [setup.cfg](../setup.cfg) targets security-critical helpers (db_utils, path_validator, auth middleware, api_agent SSRF). Last run 65% killed on path_validator.
- **Target:** Expand to LLM output validation + sandbox.
- **Gap:** Narrow scope. P2.

#### NFR-MAINT-004 · Property-based testing — *Partial · P2*
- **Now:** Hypothesis used in `tests/contracts/test_openapi_schemathesis.py`; not used elsewhere.
- **Target:** Property tests for validators, sanitizers, SQL parser.
- **Gap:** Phase 2 P2.

#### NFR-MAINT-005 · CI: backend-unit + contracts + frontend-unit + e2e — *Implemented · P0*
- **Now:** [.github/workflows/test.yml](../.github/workflows/test.yml) and [.github/workflows/e2e.yml](../.github/workflows/e2e.yml).
- **Target:** + SAST + dep-scan + container scan + DAST (NFR-SEC-006/007).
- **Gap:** Phase 1 P0.

### 5.7 Deployability & Operability (NFR-DEPLOY-*)

#### NFR-DEPLOY-001 · Docker Compose stack — *Implemented · P0*
- **Now:** [docker-compose.yml](../docker-compose.yml) — 5 services (db, redis, backend, worker, frontend); two networks (backend, db); 127.0.0.1-bound ports; memory limits (db 1G / redis 512M / backend 4G / worker 4G / frontend 512M); restart `on-failure:5`.
- **Acceptance:** `./start_app.sh` brings up stack from clean clone.

#### NFR-DEPLOY-002 · Setup wizard — *Implemented · P0*
- **Now:** [scripts/setup_wizard.py](../scripts/setup_wizard.py) — interactive `.env` generator: provider, key, model, admin creds, JWT secret (auto-gen via `secrets.token_hex(32)`), DB password.
- **Acceptance:** First run on fresh clone produces functional `.env`.

#### NFR-DEPLOY-003 · Container egress allowlist — *Implemented · P0*
- **Now:** [docker-entrypoint.sh](../docker-entrypoint.sh) installs iptables OUTPUT allowlist (loopback / DNS / docker-internal / LLM hosts). Configurable via `INZYTS_NETWORK_ISOLATION`, `INZYTS_EGRESS_ALLOWLIST`, `INZYTS_INTERNAL_HOSTS`. Auto-allows `host.docker.internal` for Ollama default.
- **Acceptance:** Curl from container to non-allowlisted host times out.

#### NFR-DEPLOY-004 · Non-root container user — *Implemented · P0*
- **Now:** `inzyts` user (no home); `gosu` privilege drop in entrypoint; ownership fix on bind mounts.
- **Acceptance:** `whoami` inside container = `inzyts`.

#### NFR-DEPLOY-005 · Kubernetes-ready (Helm + Terraform) — *Planned · P3*
- **Target:** Helm chart + Terraform module for K8s deployment.
- **Gap:** Compose only. Phase 3 P3.

#### NFR-DEPLOY-006 · Canary deployment — *Planned · P3*
- **Target:** Argo Rollouts (post-K8s).
- **Gap:** Phase 3 P3.

### 5.8 Compliance (NFR-COMP-*)

#### NFR-COMP-001 · GDPR readiness — *Partial · P1*
- **Now:** Audit + RBAC + per-job ownership + ownership-based job filter; PII detection at export.
- **Target:** DSAR endpoints (`FR-ADMIN-005`); pre-LLM PII masking opt-in (`FR-REPORT-003` evolution); retention policy.
- **Gap:** Phase 2 P1.

#### NFR-COMP-002 · SOC 2 Type 1 — *Planned · P2*
- **Target:** Controls evidenced ≥80% by end Phase 2; audit started.
- **Dependencies:** SSO, secrets manager, SIEM, SAST/DAST, IR playbook.
- **Gap:** Phase 2 P1.

#### NFR-COMP-003 · SOC 2 Type II — *Planned · P3*
- **Target:** 6-month evidence period after Type 1.
- **Gap:** Phase 3 P2.

#### NFR-COMP-004 · HIPAA — *Deferred · P3*
- **Target:** Demand-driven; BAA + envelope encryption + PHI handling + audit retention SLA.
- **Gap:** Deferred to first paying healthcare customer.

#### NFR-COMP-005 · ISO 27001 — *Deferred · P3*
- **Target:** ISMS, risk register, policies.
- **Gap:** Phase 3+.

### 5.9 Cost Management (NFR-COST-*)

#### NFR-COST-001 · Hard cost budgets per user/team — *Planned · P0*
- **Now:** None — cost tracked but not capped.
- **Target:** Default-on; configurable by admins; reject `/analyze` if user/team over budget.
- **Gap:** Whole feature. Phase 1 P0.
- **Acceptance:** (i) admin sets $50/mo/user budget; (ii) 51st-dollar request → 402 Payment Required with informative payload; (iii) admin can override.

#### NFR-COST-002 · Cost-overrun alerts — *Planned · P0*
- **Target:** Webhook + UI alert at 80% / 100% of budget.
- **Gap:** Whole feature. Phase 1 P0.

#### NFR-COST-003 · Multi-LLM router for cost optimization — *Planned · P1*
- See FR-AGENT-003.

---

## 6. Data Model & Contracts

### 6.1 Database Tables (Postgres)

Source: [src/server/db/models.py](../src/server/db/models.py) + Alembic migrations in [alembic/versions/](../alembic/versions/).

| Table | Purpose | Key columns | Indexes | Migrations |
|---|---|---|---|---|
| **jobs** | Core job records | id (PK), user_id (FK), status, mode, title, csv_path, csv_hash, multi_file_input (JSON), dict_path, target_column, analysis_type, question, result_path, error_message, logs_location, executive_summary (JSON), token_usage (JSON), cost_estimate (JSON), cost_breakdown (JSON), created_at, updated_at | id, created_at, status, csv_hash, user_id | c0c2c7f0dafe → c1d2e3f4a5b6 |
| **users** | User accounts | id (PK), username (unique), email (unique), hashed_password, is_active, role (enum: admin/analyst/viewer), created_at | id, username, email | 60691bf1c8db, 4e69b3cf3724 |
| **job_progress** | Persistent audit of progress (mirror of Redis) | id, job_id (FK), phase, progress, message, timestamp | id, job_id | 9f8bc5f56322, 01a999b9017e |
| **conversation_messages** | Follow-up Q&A history | id, job_id (FK), role (user/assistant), content, cells (JSON), created_at | id, job_id | f3a7b2c8d901 |
| **audit_logs** | Compliance audit trail | id, timestamp, user_id, username, action, resource_type, resource_id, detail, ip_address, status_code, method, path | timestamp, user_id, username, action | 4e69b3cf3724 |
| **cell_execution_audit** | Per-cell sandbox forensics | id, timestamp, job_id (FK), user_id, code_hash, code_length, duration_ms, success, error_name, killed_reason, policy_name | timestamp, job_id, user_id | d2e3f4a5b6c7 |
| **profile_cache** | DB-backed mirror of file cache | csv_hash (PK), profile_data (JSON), quality_score, created_at, access_count | csv_hash | 9f8bc5f56322 |
| **projects** | Legacy; not actively used | id, name, created_at | id | c0c2c7f0dafe |

**Future tables (planned):** `datasets` (FR-DATA-008), `workspaces` + `workspace_members` (FR-WS-001 …; not yet specified), `webhooks` (FR-REPORT-006), `llm_call_audit` (FR-AGENT-004), `job_events` (FR-RT-003).

### 6.2 Inter-Agent Handoff Schemas (Pydantic)

Source: [src/models/handoffs/](../src/models/handoffs/) (re-exported via [src/models/_handoffs.py](../src/models/_handoffs.py)).

```
UserIntent
  → OrchestratorToProfilerHandoff
    → ProfilerToCodeGenHandoff               (logical spec, mutable)
      → ProfileCodeToValidatorHandoff        (cells + manifest)
        → ProfileToStrategyHandoff           ← FROZEN; integrity-hashed
          ├→ ExploratoryConclusionsOutput    (Exploratory mode)
          └→ StrategyToCodeGenHandoff
             → AnalysisCodeToValidatorHandoff
               → FinalAssemblyHandoff
```

Plus mode-specific extensions: `ForecastingExtension`, `ComparativeExtension`, `DiagnosticExtension`, `RootCauseStrategy`, `DimensionalityStrategyHandoff`.

### 6.3 REST API Schemas

Source: [src/server/models/schemas.py](../src/server/models/schemas.py). Key types: `AnalysisMode` (enum), `AnalysisRequest`/`AnalysisResponse`, `JobSummary`/`JobStatusResponse`, `LogEntry`, `ColumnProfileResponse`, `CostBreakdownResponse`, `CellEditRequest`/`Response`, `FollowUpRequest`/`Response`, `ConversationHistoryResponse`, `ReportExportRequest`, `ExecutiveSummaryResponse`, `PIIScanResponse`, `ModeSuggestionRequest`/`Response`, `DBTestRequest`/`Response`, `SQLPreviewRequest`, `APIPreviewRequest`.

### 6.4 Socket.IO Events

| Event | Direction | Payload | Use |
|---|---|---|---|
| `connect` / `disconnect` | client→server | implicit | Auth handshake |
| `join_job` | client→server | `{job_id}` | Subscribe to room (ownership-validated) |
| `log` | server→room | `{timestamp, level, message}` | Streamed, credential-scrubbed |
| `progress` | server→room | `{progress, message, phase, elapsed_seconds, eta_seconds, phase_timings}` | Phase progress bar |
| `phase_update` | server→room | `{job_id, phases: PhaseStatus[]}` | Per-agent status |
| `metrics_snapshot` | server→room | `RunMetrics` (tokens, cost, elapsed, agents, quality) | Cost/agent meters |
| `agent_event` | server→room | `{type, event, phase?, agent?, status?, data}` | Agent lifecycle |
| `cell_status` / `cell_output` / `cell_complete` | server→room | per cell | Live notebook streaming |

### 6.5 Configuration Surface

Source: [src/config/__init__.py](../src/config/__init__.py); env prefix `INZYTS__`, nested delimiter `__`.

Critical env groups (full list in [config/.env.example](../config/.env.example)):

| Group | Vars | Required |
|---|---|---|
| LLM | `INZYTS__LLM__DEFAULT_PROVIDER`, `INZYTS__LLM__{ANTHROPIC,OPENAI,GOOGLE}_API_KEY`, model overrides | At least one provider |
| Database | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`, `DB_MAX_RETRIES`, `DB_RETRY_INTERVAL` | Yes |
| Redis | `REDIS_URL` | Yes |
| Auth | `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `INZYTS_API_TOKEN`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` | All except algorithm |
| Network isolation | `INZYTS_NETWORK_ISOLATION`, `INZYTS_EGRESS_ALLOWLIST`, `INZYTS_INTERNAL_HOSTS`, `INZYTS_ALLOW_HOST_DOCKER_INTERNAL`, `INZYTS_DB_URI_ALLOW_LOOPBACK` | No (strict by default) |
| File paths | `UPLOAD_DIR`, `DATASETS_DIR`, `INZYTS__OUTPUT_DIR`, `LOG_DIR` | No |
| Limits | `SQL_MAX_ROWS` (200K), `SQL_MAX_COLS` (500), `CLOUD_MAX_DOWNLOAD_MB` (500), `API_MAX_RESPONSE_SIZE` (100MB), `API_TIMEOUT` (30s) | No |
| CORS | `ALLOWED_ORIGINS` | No |
| LLM tuning | `temperature` (0.1), `max_tokens` (8192) | No |

---

## 7. Constraints & Assumptions

### 7.1 Operational constraints

- **Single-tenant by default.** Multi-tenancy via workspaces + RLS is roadmapped (Phase 2 P0).
- **Operator-supplied TLS.** No built-in TLS termination; production deployments assume nginx (or equivalent) reverse proxy.
- **Operator-managed secrets.** `.env` is the current secret store; no built-in rotation.
- **Beta status.** v0.10.0 is labelled Beta; APIs are versioned (`/api/v2`) with v3 planned (Phase 3 P2).
- **Linux + macOS + Windows** via Docker Desktop / WSL 2.

### 7.2 Technical assumptions

- Python ≥3.10; Node 20; Postgres 15; Redis 7.
- Modern browser (Chromium / Firefox / Safari current). No legacy IE support.
- LLM provider has stable API and pricing (token costs hardcoded in [cost_estimator.py](../src/server/services/cost_estimator.py); revisit on provider price changes).
- Sandbox assumes Linux kernel features (`setsid`, RLIMIT_*, process groups). Non-Linux fallbacks are best-effort.

### 7.3 Behavioral guarantees

- The Profile Lock is a hard contract: Phase 2 cannot start without it. This intentionally prevents hallucination drift.
- LLM-generated code only runs in the sandbox — never directly in the worker process.
- Audit logs are write-only from the application's perspective (no API to delete; only query).
- File uploads land outside the application source tree (`data/uploads/`) and are validated for path traversal.

### 7.4 Out of scope for v0.10.0 → v1.0

- Streaming / CDC ingestion (Kafka, Debezium) — parking lot, batch + dataset-as-object covers 95%.
- Geospatial mode (10th) — parking lot.
- Deep-learning mode — parking lot; FLAML AutoML is the cheaper first step.
- Voice-first follow-up (Whisper STT/TTS) — parking lot until MCP traction.
- Edge / ONNX export — parking lot until model-serving demand.
- Active learning from corrections — defer until P3 baseline established.

---

## 8. Open Questions & Known Gaps

### 8.1 Critical (P0, Phase 1) — must close to ship "Trust" bet

| Ref | Gap |
|---|---|
| FR-RT-002 | SSE-streamed agent reasoning |
| NFR-COST-001 | Hard cost budgets per user/team |
| FR-AGENT-002 | Confidence scoring on conclusions |
| FR-DATA-008 | Dataset-as-first-class object + dedup library |
| FR-LLM-003 | MCP server |
| FR-AGENT-005 | LLM output validation maturation |
| NFR-SEC-011 | Prompt-injection regression corpus expansion |
| NFR-SEC-006 | SAST + dep-scan in CI |
| NFR-SEC-012 | Sandbox-escape adversarial CI test ungated |
| FR-UI-013 | Confidence chip on UI |
| FR-UI-014 | Real-time cost meter UI |
| NFR-SEC-005 | Secrets manager |

### 8.2 Important (P1, Phase 2) — must close to ship "Sellability" bet

| Ref | Gap |
|---|---|
| FR-UI-017 | Dashboard builder (pinned cells) |
| (workspaces) | Team workspaces + role-based sharing — full FR set TBD |
| (sharing) | Share-by-link (public/private read-only) — full FR set TBD |
| FR-AUTH-001 evolution | SSO (OIDC / SAML) + MFA |
| NFR-SEC-008 | PostgreSQL row-level security |
| FR-ADMIN-005 | GDPR DSAR endpoints |
| NFR-OBS-006 | OpenTelemetry tracing |
| FR-WF-006 | Versioned handoff schemas |
| FR-AGENT-003 | Multi-LLM router |
| (mode) | Anomaly detection (8th) |
| (MLOps) | MLflow auto-logging |
| FR-CACHE-002 | Phase-2 result cache |
| FR-DATA-007 | Delta / Iceberg ingestion |
| FR-DATA-001 evolution | Multi-sheet Excel ingestion |
| FR-REPORT-005 | Word + Python-script export |
| FR-REPORT-006 | Webhook notifications |
| (history) | Run history with diff view |
| (scheduler) | Scheduled runs (cron) |

### 8.3 Strategic (P1–P2, Phase 3) — must close to ship "Leverage" bet

| Ref | Gap |
|---|---|
| FR-AGENT-001 evolution | Plugin / agent SDK with manifests |
| (RAG) | Cross-run memory via pgvector |
| NFR-OBS-006 evolution | OpenLineage emission per agent step |
| NFR-SEC-010 | gVisor / Firecracker sandbox upgrade |
| NFR-COMP-002 | SOC 2 Type 1 audit |
| (mode) | NLP / text mode (9th) |
| (mode) | Fairness / bias audit module |
| (embedded) | Embedded mode (white-label widget + JWT exchange) |
| NFR-PERF-004 | Worker autoscaling (KEDA) |
| (marketplace) | Plugin marketplace |
| (etl) | Reverse ETL |
| (api) | API v3 with deprecation contract |
| (compliance) | Compliance evidence dashboard |

### 8.4 Open product/architecture questions

1. **Workspace data model.** When workspaces land, do datasets, jobs, notebooks, dashboards all sit under workspace, or only some? Implications for RLS predicates.
2. **MCP authentication.** Same JWT path as REST, or per-MCP-session token issuance? Phase 1 risk per [FUTURE_ROADMAP.md](FUTURE_ROADMAP.md#top-risks-per-phase).
3. **Plugin SDK ABI.** Versioned handoffs first, then plugins? Roadmap suggests yes — confirm before Phase 3.
4. **Pre-LLM PII masking quality impact.** Opt-in per column with A/B against unmasked, but what's the default for new tenants?
5. **Cost-budget admin override semantics.** Soft override (one-time) vs hard override (raises budget) — UX call.
6. **Phase-2 cache key.** `(profile_hash, mode, question)` is a coarse key. Should it include `target_column`, `exclude_columns`, `dict_path`? Likely yes; specify before implementation.

---

## 9. Glossary

| Term | Definition |
|---|---|
| **Agent** | An LLM-driven worker with a single responsibility (e.g., Profiler, Strategy, Validator). 27 in v0.10.0. |
| **Analysis Mode** | One of seven user-selectable analysis pipelines: Exploratory, Predictive, Diagnostic, Comparative, Forecasting, Segmentation, Dimensionality. Two more (Anomaly, NLP) are roadmapped. |
| **Cell** | An executable unit in a Jupyter notebook (code or markdown). |
| **Cell-edit Agent** | The LLM agent that mutates a single cell from a natural-language instruction. |
| **CrewAI** | Agent-coordination framework used internally in some agents. |
| **DSAR** | Data Subject Access Request — the GDPR right to export or delete personal data. |
| **Extension Agent** | A pre-strategy enrichment agent for Forecasting / Comparative / Diagnostic modes. |
| **Follow-up Agent** | The LLM agent that answers questions about a completed analysis. |
| **Handoff** | An immutable Pydantic schema passed between agents. The Profile→Strategy handoff is the strictest (frozen + integrity-hashed). |
| **Ink Black** | The frontend's dark-themed visual identity (cobalt + French blue + sky aqua over a deep-twilight base). |
| **KernelSandbox** | The process-group-isolated execution environment for LLM-generated code. See FR-SBX-*. |
| **LangGraph** | The state-machine library that wires the 27 agents into a workflow. |
| **MCP** | Model Context Protocol — Anthropic's tool-exposure protocol. Inzyts plans to expose itself as an MCP server (FR-LLM-003). |
| **PIPELINE_MODE** | Internal enum for analysis modes; mapped from API `AnalysisMode` enum via `_MODE_VALUE_MAP`. |
| **Profile Lock** | The frozen Phase-1 handoff that prevents Phase-2 hallucination. Integrity-hashed. |
| **Profile Cache** | The 7-day file+DB cache of Phase-1 results, keyed by CSV content hash. |
| **Phase 1 / Phase 2** | The two halves of a run: Phase 1 = Data Understanding (profile + lock); Phase 2 = Analysis & Modeling. Exploratory mode skips Phase 2. |
| **RBAC** | Role-Based Access Control. Three tiers in v0.10.0: Admin > Analyst > Viewer. |
| **RLS** | Row-Level Security — a Postgres feature for per-row authorization. Roadmapped (NFR-SEC-008). |
| **Sandbox** | See KernelSandbox. |
| **Sandbox Policy** | A configuration object on `KernelSandbox` controlling resource limits, timeout, allowlists. PRODUCTION_POLICY vs DEVELOPMENT_POLICY. |
| **Strategy Agent** | The Phase-2 agent that designs the analysis plan for a given mode (different agent per mode). |
| **Validator** | An agent that runs generated cells, scores quality, and decides whether to retry, lock, or proceed. |

---

**End of SPEC v0.1.0.**

Maintain this document alongside code changes: when behavior changes, update the corresponding FR/NFR's Now/Target/Gap fields; bump the change log in §1.6; never silently renumber IDs.
