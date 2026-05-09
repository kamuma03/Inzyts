# Inzyts Future Enhancement Roadmap

**Comprehensive Multi-Perspective Product Roadmap**

**Version**: 6.0.0
**Last Updated**: 2026-04-28
**Status**: Strategic Planning Document
**Horizon**: 12 months (rolling)
**Baseline**: v0.10.0

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Product Context (Current State)](#product-context-current-state)
3. [Strategic Bets](#strategic-bets)
4. [Perspective 1: Product Manager](#perspective-1--product-manager)
5. [Perspective 2: UI/UX Designer](#perspective-2--uiux-designer)
6. [Perspective 3: Software Architect](#perspective-3--software-architect)
7. [Perspective 4: End User Voices](#perspective-4--end-user-voices)
8. [Perspective 5: Innovation & Growth Strategist](#perspective-5--innovation--growth-strategist)
9. [Perspective 6: Data Engineer](#perspective-6--data-engineer)
10. [Perspective 7: Data Scientist / ML Engineer](#perspective-7--data-scientist--ml-engineer)
11. [Perspective 8: Security Engineer](#perspective-8--security-engineer)
12. [Unified 12-Month Plan](#unified-12-month-plan)
13. [Dependencies, Gates, Risks, Metrics](#dependencies-gates-risks-metrics)
14. [Parking Lot](#parking-lot)
15. [Appendix: Perspective Interaction Map](#appendix-perspective-interaction-map)

---

## Executive Summary

Inzyts v0.10.0 is a **27-agent autonomous data analysis system** with a 7-mode pipeline, smart caching, self-correcting validators, JWT + RBAC + audit logging, multi-source ingestion (CSV / SQL / cloud storage / REST APIs / cloud DWH), report export (PDF / HTML / PPTX / Markdown) with executive summaries and PII detection, an interactive notebook viewer, conversational follow-up, and a hardened Docker deployment. The work to make Inzyts an *individually credible analysis tool* is largely done.

The next 12 months are about making Inzyts **trustworthy at team scale, distributable through ecosystems, and architecturally ready for the modes that come after the current 7**. This roadmap collapses the prior four-quarter / four-version plan (v2.0 → v3.0) into **three rolling phases**, each ~3–4 months. Items that shipped in v0.10.0 are no longer roadmap items — they are baseline.

### What changed since the previous roadmap (v5.0.0, 2026-03-10)

- No new features merged in 7 weeks; effort went to test-suite consolidation, doc refresh, and removing dead Jupyter references.
- Stale-risk on the v2.1.0 → v3.0.0 critical path (dashboards, workspaces, MLflow, SSO) is rising.
- New highest-leverage opportunities surfaced from the codebase audit: **SSE-streamed agent reasoning**, **cost budgets per user**, **dataset-as-first-class-object**, **MCP server integration**, **plugin/agent SDK with versioned handoffs**, **confidence scoring on conclusions**.

### Three bets that unlock the rest

1. **Trust** — SSE streaming + confidence scoring + cost budgets. Converts "feels slow / feels mysterious / feels risky" into "feels intelligent and bounded."
2. **Sellability** — Dashboards + team workspaces + SSO. Without these, the Team-tier monetization story doesn't close.
3. **Leverage** — Plugin/agent SDK with versioned handoffs + MCP server. Turns Inzyts from a fixed 27-agent monolith into a platform; places it inside the Claude / IDE ecosystems for distribution.

### Critical Gap Snapshot

| Area | Current State (v0.10.0) | Gap | Target State |
|------|--------------------------|-----|--------------|
| Authentication | JWT + bcrypt + RBAC + audit logging + rate limiting | 🟡 Important | SSO (OIDC/SAML) + MFA + secrets manager |
| Reporting | PDF / HTML / PPTX / MD + Executive Summary + PII detection | 🟢 Mature | Word + dashboards |
| Dashboards | None | 🔴 Critical | Interactive builder on top of existing notebook outputs |
| Collaboration | Single-user | 🔴 Critical | Team workspaces + share-by-link + comments |
| Data Sources | CSV + SQL (PG/MySQL/MSSQL/BQ/Snowflake/Redshift/Databricks) + S3/GCS/Azure + REST APIs | 🟢 Mature | Delta/Iceberg + dataset-as-object |
| MLOps | Cost tracking per job | 🟡 Important | MLflow + registry + confidence/fairness gates |
| Advanced AI | Traditional ML (7 modes) | 🟡 Important | Anomaly + NLP modes; RAG over past runs |
| Trust UX | Black-box during run | 🔴 Critical | Streamed reasoning + confidence scores |
| Cost guardrails | Tracked per job, not capped | 🔴 Critical | Hard per-user/team budgets |
| Distribution | Web UI + REST API | 🟡 Important | MCP server, embedded mode, agent marketplace |

---

## Product Context (Current State)

| Attribute | Details |
|-----------|---------|
| **Product Name** | Inzyts |
| **Current Version** | v0.10.0 (Beta) |
| **Core Problem Solved** | Eliminates manual data exploration; transforms raw CSV/SQL/cloud data into comprehensive, executable Jupyter notebooks autonomously |
| **Target Users** | Data Analysts, Data Scientists, Business Analysts, Product Managers, Enterprise Teams |
| **Architecture** | 27-agent LangGraph orchestration with 7-mode pipeline |
| **Tech Stack** | Python / FastAPI / PostgreSQL / Redis / Celery + React / TypeScript / Vite |
| **LLM Support** | Anthropic Claude (primary), OpenAI, Google Gemini, Ollama |
| **Test Coverage** | ~108 test files across unit / integration / e2e / security / safety / performance / contract / accessibility / UI |
| **Data Sources** | CSV, JSON, Excel, Parquet · PG / MySQL / MSSQL · BigQuery / Snowflake / Redshift / Databricks · S3 / GCS / Azure Blob · REST APIs |
| **Authentication** | JWT (bcrypt) + 3-tier RBAC (Admin / Analyst / Viewer) + per-job ownership + audit logging + rate limiting (slowapi) |
| **Sandbox** | KernelSandbox: process-group SIGKILL, network egress block, secret stripping, allowlist imports, 60s/cell timeout |
| **Interactive** | Conversational follow-up agent, cell-level natural-language editing, live notebook execution via WebSocket |
| **Reporting** | PDF (WeasyPrint), HTML (Jinja2), PPTX (python-pptx), Markdown — with LLM-generated executive summary and regex PII detection/masking |
| **Observability** | Phase tracker + Redis-backed timing + Socket.IO progress events + per-job cost tracking |
| **Compliance** | None certified; controls in place align toward SOC 2 Type 1 / GDPR readiness |
| **Deployment** | Docker Compose (7 services) — non-root containers, network isolation, resource limits |

---

## Strategic Bets

Three commitments that should drive prioritization for the next 12 months.

### Bet 1 — "Trust"
**Hypothesis:** Inzyts already produces good answers; the bottleneck for adoption is whether users *trust them and feel in control*.

**Initiatives that count:**
- Stream agent reasoning live (SSE) — collapsible thought panel during runs.
- Confidence scoring on every conclusion (self-consistency + agreement).
- Hard cost budgets per user/team (default-on, configurable by admins).
- Fairness / bias audit module on Phase 2 outputs.

**Win condition:** median user reports "I know what's happening, what it cost me, and how confident the conclusion is" by end of Phase 1.

### Bet 2 — "Sellability"
**Hypothesis:** Every paid tier above Pro requires a team-shaped artifact (dashboards, share-by-link, SSO). Without these, Inzyts is a single-seat product.

**Initiatives that count:**
- Dashboard builder on top of pinned notebook cells (don't try to rebuild Tableau).
- Team workspaces with role-based sharing.
- SSO (OIDC + SAML) and secrets manager replacing `.env`.
- SOC 2 Type 1 audit prep started by end of Phase 2.

**Win condition:** ≥10 design-partner orgs on Team tier by end of Phase 2.

### Bet 3 — "Leverage"
**Hypothesis:** A 27-agent monolith doesn't scale to verticals. Inzyts wins long-term if external developers can extend it and if it lives inside other tools' workflows.

**Initiatives that count:**
- Plugin / agent SDK with versioned handoff schemas.
- MCP server exposing Inzyts as a tool to Claude Desktop / IDE clients.
- Dataset-as-first-class-object (precondition for cross-run memory and templates).
- RAG over past runs ("we've analyzed this before — here's what changed").

**Win condition:** ≥5 third-party plugins published and ≥1 named Anthropic-ecosystem placement by end of Phase 3.

---

## Perspective 1: 🎯 Product Manager

**Focus:** Market fit, user value, business impact

### Gap Analysis vs Competitors (Dataiku, DataRobot, Hex, Mode)

| Area | Inzyts v0.10.0 | Competitors | Gap |
|------|----------------|-------------|-----|
| Data Sources | CSV / SQL / cloud DWH / cloud storage / REST | + streaming (Kafka/CDC) | 🟢 Streaming only |
| Authentication | JWT + RBAC + audit + rate limit | + SSO + MFA | 🟡 SSO/MFA |
| Reporting | PDF / HTML / PPTX / MD + Exec Summary + PII | + Word + Dashboards | 🟡 Dashboards |
| Collaboration | Single-user | Workspaces / sharing / comments | 🔴 Critical |
| MLOps | Cost tracking | MLflow / registry / serving | 🟡 Important |
| Trust UX | Phase progress only | Streamed reasoning, confidence | 🔴 Critical |
| Cost Guardrails | Tracked, uncapped | Per-user budgets | 🔴 Critical |
| Autonomous Agents | ✅ 27-agent system | Limited automation | 🟢 Advantage |
| Profile Lock | ✅ Anti-hallucination | Not common | 🟢 Advantage |
| Conversational AI | ✅ Follow-up + cell editing | Limited chat | 🟢 Advantage |
| Distribution | Web UI + REST | + Embedded + marketplace | 🟡 Important |

### User Jobs-to-be-Done (Unmet)

| User Type | Unmet Need | Impact |
|-----------|------------|--------|
| Data Analyst | "I need to share polished, interactive dashboards with stakeholders." | High |
| Data Scientist | "I want to track experiments and compare runs over time." | High |
| Data Scientist | "I want to know how confident the LLM is in this conclusion." | Critical |
| Business User | "I want to embed an Inzyts dashboard in our internal portal." | Medium |
| Enterprise Admin | "I need SSO and per-user cost budgets before procurement signs." | Critical |
| Team Lead | "I need visibility into what my team has analyzed and what changed." | Medium |
| Power User | "I want to schedule weekly refreshes and diff against last week's run." | Medium |

### Feature Prioritization (RICE — refreshed for 2026-04-28)

| Feature | Reach | Impact | Confidence | Effort | Score | Priority |
|---------|-------|--------|------------|--------|-------|----------|
| SSE-streamed agent reasoning | 8K | 6 | 90% | S | 432 | **P0** |
| Cost budgets per user/team | 4K | 8 | 90% | S | 576 | **P0** |
| Dashboard builder (pinned cells) | 6K | 9 | 75% | L | 405 | **P0** |
| Team workspaces + share-by-link | 5K | 8 | 80% | M | 320 | **P0** |
| MCP server (Inzyts as a tool) | 5K | 6 | 90% | S | 270 | **P0** |
| Confidence scoring on conclusions | 7K | 8 | 80% | M | 373 | **P0** |
| SSO (OIDC/SAML via WorkOS / Authentik) | 2K | 9 | 85% | M | 153 | **P1** |
| Webhook notifications (Slack/Teams/HTTP) | 6K | 5 | 95% | S | 285 | **P1** |
| MLflow auto-logging | 2K | 7 | 80% | M | 112 | **P1** |
| Anomaly detection mode (8th) | 3K | 7 | 80% | M | 168 | **P1** |
| Dataset-as-object + library | 8K | 6 | 85% | M | 408 | **P0** |
| Plugin / agent SDK | 3K | 8 | 70% | L | 168 | **P1** |
| NLP / text mode (9th) | 3K | 7 | 75% | L | 52 | **P2** |
| Geospatial mode | 2K | 7 | 60% | L | 42 | **P3** |
| Word (.docx) export | 4K | 4 | 95% | S | 304 | **P1** quick win |
| Notebook → Python script export | 4K | 4 | 95% | S | 304 | **P1** quick win |
| Scheduled runs (cron) + diff view | 3K | 7 | 75% | M | 79 | **P2** |

### Monetization Tiers (refined)

| Tier | Differentiator | Target | Price |
|------|----------------|--------|-------|
| **Free** | Exploratory mode, 10 runs/mo, single user | Individual analysts | $0 |
| **Pro** | All 7 modes, unlimited runs, all exports, SSE streaming, cost budget | Power users | $49/mo |
| **Team** | Workspaces, dashboards, share-by-link, SQL/cloud DWH, webhooks | Small teams (5–20 seats) | $199/mo |
| **Enterprise** | SSO, RBAC + audit, secrets manager, SOC 2 evidence, SLA, BAA option | Large orgs | Custom |

**Critical:** Team tier is unsellable today. Phase 2 must close *all three* of dashboards / workspaces / SSO to unlock it.

### KPIs to Track

| Feature | KPI | Target by end of Phase |
|---------|-----|------------------------|
| SSE streaming | Median perceived time-to-first-output | < 30 s (Phase 1) |
| Cost budgets | Cost-overrun incidents | 0 (Phase 1) |
| Dashboards | Dashboard creations / month | 100+ (Phase 2) |
| Workspaces | Active team workspaces | 50+ (Phase 2) |
| SSO | Enterprise prospects unblocked | 5+ (Phase 2) |
| Confidence scoring | Median conclusion confidence shown | ≥0.7 displayed (Phase 1) |
| Plugin SDK | 3rd-party plugins published | 5+ (Phase 3) |
| MCP server | Active MCP-connected sessions | 200+/mo (Phase 1) |

### Quick Wins (<2 weeks)

| Feature | Business Value | Status |
|---------|---------------|--------|
| SSE-streamed reasoning | High (perceived speed + trust) | Phase 1 |
| Cost budgets per user | High (risk mitigation) | Phase 1 |
| Webhook notifications | Medium (integration) | Phase 1 |
| Word (.docx) export | Medium (audience parity with PPTX) | Phase 1 |
| Notebook → Python script export | Medium (DS productionization path) | Phase 1 |
| Cmd-K command palette | Medium (power-user retention) | Phase 1 |
| Run history with diff | Medium (cross-run continuity) | Phase 2 |

---

## Perspective 2: 🎨 UI/UX Designer

**Focus:** Usability, accessibility, delight

### UX Friction Points (current → proposed)

| Friction | Current | Proposed | Impact | Cx |
|----------|---------|----------|--------|----|
| Long-running job feedback | Phase progress bar; no token-by-token visibility | Stream agent reasoning via SSE; collapsible thought panel | High | S |
| First-run confusion | Smart Mode Suggestion exists but post-question | 30-second onboarding tour + sample dataset gallery | High | S |
| Notebook viewer density | Flat cell list | Collapsible sections per phase + pinned TL;DR card | Med | M |
| Error messages | Sanitized, no remediation | "What to try next" + copy-debug-bundle button | Med | S |
| Mobile / tablet | Desktop-only effectively | Read-only mobile view (history + share links + report download) | Med | M |
| WCAG 2.1 audit | Tests scaffolded; depth unknown | Color contrast on Ink Black + keyboard nav across InteractiveCell + ARIA labels on charts | High | M |
| PII warning UX | Banner exists | Inline highlight in preview; click-to-mask | Med | S |
| Keyboard shortcuts | Mostly absent | Cmd-K palette: jump to job, re-run, ask follow-up, switch mode | Med | M |
| Cost visibility | Per-job cost in metadata only | Real-time cost meter during run; budget bar per user | High | S |
| Confidence indicator | None | Confidence chip on each conclusion card (Low / Med / High + tooltip) | High | M |

### Information Architecture (proposed)

```
Home
├── My Workspace
│   ├── Datasets (NEW — first-class object)
│   ├── Runs (history + diff)
│   ├── Dashboards (NEW)
│   └── Shared with me (NEW)
├── New Analysis
│   ├── Pick dataset (or upload / connect)
│   ├── Configure (mode + question, with smart suggest)
│   └── Run (SSE-streamed reasoning + cost meter)
└── Admin (RBAC-gated)
    ├── Users · Roles
    ├── Audit logs
    ├── Cost budgets
    └── Connectors (SSO, secrets manager)
```

### Accessibility Gaps (WCAG 2.1)

| Issue | Current | Fix |
|-------|---------|-----|
| Color contrast | Some text < 4.5:1 in Ink Black | Audit with axe-core; bump non-compliant tokens |
| Screen reader on charts | Charts unlabelled | Auto-generate alt text from LLM cell metadata |
| Keyboard nav focus traps | Modals trap focus poorly | Standardize Radix focus management |
| Motion | Animations not reducible | Respect `prefers-reduced-motion` globally |
| Notebook chart alt-text | Missing | Augment cell render with chart description string |

### Data Visualization UX

| Improvement | Current | Proposed |
|-------------|---------|----------|
| Chart export | Embedded only | PNG/SVG download per chart |
| Chart annotations | None | Click-to-annotate; annotations persist with run |
| Dashboard filters | None (no dashboards) | Cross-cell filter controls in dashboard builder |
| Color blindness | Default matplotlib | Colorblind-safe defaults; per-user preference |
| Chart accessibility | None | LLM-generated chart summaries surfaced to screen readers |

---

## Perspective 3: 🏗️ Software Architect

**Focus:** Scalability, maintainability, technical excellence

### Technical Debt Inventory

| Initiative | Problem | Architecture Impact | Risk | Effort |
|------------|---------|---------------------|------|--------|
| Sandbox upgrade to gVisor / Firecracker | Current `KernelSandbox` is process-group based; LLM-generated code escape blast radius is the host container | Strong isolation; enables "code-execution-as-a-service" sale | Med (perf, packaging) | L |
| Plugin / agent SDK | All 27 agents hardcoded in `graph.py`; new modes require core edits | External agents loadable via manifest; community plugins | Med (interface stability) | L |
| Versioned handoff schemas (`v1`, `v2`) | Single-version Pydantic models; future agent changes break | Migration path; backward compat | Low | M |
| Structured event log + tail API | Progress is emitted via Socket.IO but not stored | Replayable runs, post-hoc debug, audit-friendly | Low | M |
| Multi-LLM router with fallback + per-task routing | `agent_factory` returns one LLM globally | Cost optimization (cheap model for routing, premium for codegen) | Low | M |
| OpenTelemetry tracing across agents | Per-job logs; no per-agent spans | Find slow agents; SLO-able | Low | M |
| Postgres row-level security | Per-job ownership in Python only | Defense in depth; multi-tenant precondition | Med | M |
| Worker autoscaling (Celery → KEDA) | Static concurrency | Cost-aware scaling; Phase 2 jobs are spiky | Low | M |
| Centralized retry policy object | Each validator hand-codes retry budget | Consistent semantics, observable | Low | S |
| Secrets manager integration | `.env` proliferation; JWT secret in plaintext | Required for SOC 2; drop-in for Vault / AWS Secrets | Low | M |
| API v3 with explicit deprecation contract | v2 grew organically | Reduce SDK breakage | Low | M |
| Cache layer hardening | Mixed file + Redis cache | Single Redis-backed cache with TTL policy + hash-based invalidation | Low | M |

**Architectural keystone for the next 12 months:** the **plugin SDK + versioned handoffs + structured event log** triad. Without them, every new mode (anomaly, NLP, geospatial, deep learning) is a fork in `src/workflow/graph.py`, and every audit / replay request is a forensic exercise.

### Scalability Bottlenecks

| Component | Current Limit | At 10× | At 100× | Fix |
|-----------|---------------|--------|---------|-----|
| Celery workers | Static concurrency | Queue backlog | System failure | KEDA autoscaling |
| PostgreSQL | Single instance | Connection-pool exhaustion | DB crashes | PgBouncer + read replicas |
| Redis | Single instance | Memory overflow | Cache misses | Redis Cluster + LRU eviction |
| LLM API calls | Sequential per-agent | Rate limits | Cost explosion | Cost budgets + batching + cheap-model routing |
| File storage | Local disk | Disk full | Not scalable | Object storage (S3/GCS) for uploads + outputs |
| Sandbox kernels | Per-process limit | Memory pressure | OOM kills | Microvm-per-run with pooled warm pool |

### Architecture Evolution

```
Phase 1 (now → 3mo)              — Modular Monolith Hardening
┌──────────────────────────────────────────────────────────────┐
│ FastAPI + Celery + 27 Agents                                 │
│  + SSE streaming layer                                       │
│  + structured event log (replaces ad-hoc Socket.IO emit)     │
│  + cost budget middleware                                    │
│  + secrets manager adapter                                   │
└──────────────────────────────────────────────────────────────┘

Phase 2 (3 → 6mo)                — Tenant-Ready Service Boundaries
┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
│ Auth + SSO │ │ Analysis   │ │ Reports +  │ │ Workspaces │
│            │ │ + Agents   │ │ Dashboards │ │ + Sharing  │
└─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘
      └──── Postgres (RLS) + Redis (Cluster) + OTEL traces ────┘

Phase 3 (6 → 12mo)               — Platform & Plugin
┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
│ Core API   │ │ Plugin SDK │ │ MCP Server │ │ Embedded   │
│ (versioned)│ │ + Registry │ │            │ │ Mode       │
└─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘
      └─── Sandbox (gVisor) + Lineage (OpenLineage) ─────────┘
```

### API Improvements

| Improvement | Current | Proposed | Phase |
|-------------|---------|----------|-------|
| Versioning | `/api/v2/` | Add `/api/v3/` with versioned handoff schemas | P3 |
| Streaming | WebSocket for cell exec | + SSE for agent reasoning | P1 |
| Rate limiting | slowapi (10/min analyze, 30/min jobs) | Tiered: 100/min (Pro), 1000/min (Team) | P2 |
| Pagination | Inconsistent | Cursor-based across history endpoints | P2 |
| Error format | Sanitized strings | RFC 7807 Problem Details | P2 |
| OpenAPI spec | Auto-generated | Curated + examples + SDK gen | P2 |
| Webhooks | None | Job lifecycle webhooks (Slack/Teams/HTTP) | P1 |
| MCP | None | MCP server exposing analysis + follow-up + reports as tools | P1 |

### DevOps / Infrastructure

| Initiative | Current | Proposed | Phase |
|------------|---------|----------|-------|
| CI/CD | GitHub Actions (test workflow) | + SAST (Semgrep) + dep-scan (pip-audit, npm audit) + container scan | P1 |
| Monitoring | Basic logs | Prometheus + Grafana + AlertManager | P2 |
| Tracing | None | OpenTelemetry → Tempo / Jaeger | P2 |
| Log aggregation | Docker logs | Loki / ELK | P2 |
| Backup / recovery | Manual | Automated daily backups + PITR | P2 |
| IaC | Docker Compose | + Terraform module + Helm chart for K8s | P3 |
| Canary deployments | None | Argo Rollouts (when on K8s) | P3 |

---

## Perspective 4: 👤 End User Voices

### Power User

| Verbatim | Underlying Need | Feature Implication |
|----------|-----------------|---------------------|
| "I wish I could pin a baseline run and diff next week's run against it." | Run versioning + diff | Run history with diff view (P2) |
| "I have to re-upload the same CSV every time." | Persistence | Dataset-as-object + library (P1) |
| "It's annoying that the SQL agent picks columns I don't want." | Constrained autonomy | Column-level allow/deny per connection (P2) |
| "If only it integrated with my dbt project." | Modeling-tier integration | dbt manifest import → templates (P3) |
| "I want to schedule weekly refreshes." | Automation | Scheduled runs (cron) (P2) |
| "I run the same analysis on 50 datasets every Monday." | Bulk | Batch analysis API (P2) |
| "I want to use my own prompts for the strategy agent." | Customization | Custom agent prompt overrides (P3) |
| "I need to know if the LLM is just guessing." | Trust | Confidence scoring (P1) |

### New User

| Verbatim | Underlying Need | Feature Implication |
|----------|-----------------|---------------------|
| "I expected it to read all sheets in my Excel file." | Multi-sheet | Multi-sheet picker (P1 quick win) |
| "I almost gave up when the job ran 4 minutes with no output." | Transparency | SSE-streamed reasoning (P1) |
| "I don't understand the difference between Diagnostic and Comparative." | Education | Mode picker with worked examples + smart suggest (P1) |
| "It took me too long to find the report download." | Discoverability | Persistent Export button on every completed job (P1 quick win) |
| "I expected it to explain results in plain English." | Interpretation | Executive summary (✅ shipped) — surface more prominently |
| "I didn't know what a 'profile lock' meant." | Jargon reduction | Plain-language UI copy review (P2) |
| "There's no sample dataset to try before uploading my own." | Safe exploration | Demo dataset gallery on first run (P1) |

→ Three underlying themes cluster: **persistence** (datasets / runs / templates as first-class), **transparency** (streaming, diffs, confidence), **integration** (dbt, schedules, MCP, exports).

---

## Perspective 5: 🚀 Innovation & Growth Strategist

**Focus:** Differentiation, emerging tech, market expansion

### High-Leverage Innovations

| Innovation | Description | Differentiation | TTV | Phase |
|------------|-------------|-----------------|-----|-------|
| **MCP server** | Expose Inzyts as an MCP tool so Claude Desktop / IDE clients can drive it | 5/5 (positions in Anthropic ecosystem) | 1 mo | P1 |
| **Conversational dataset onboarding** | "Upload + describe in one sentence" → agent picks mode + question | 5/5 | 1 mo | P1 |
| **Cross-run pattern memory** | "We've analyzed this dataset before — here's what changed" via RAG over past runs | 5/5 (data moat) | 3 mo | P3 |
| **Agent / extension marketplace** | Community-contributed extension agents (vertical templates: SaaS churn, e-comm cohort, healthcare DRG) | 5/5 (network effect) | 6 mo | P3 |
| **Embedded mode (white-label widget)** | Drop Inzyts inside customer apps via iframe + JWT exchange | 4/5 (B2B2C) | 4 mo | P3 |
| **Auto-generated narrated video summaries** | TTS over Executive Summary + chart fly-throughs | 4/5 | 2 mo | P3 |
| **Voice-first follow-up** | Whisper STT → follow-up agent → TTS | 3/5 | 3 mo | P3 |
| **Agentic debugging** | Agents that debug their own failed validator output | 4/5 | 3 mo | P2 |

### Platform / Ecosystem Plays

| Strategy | Description | Potential |
|----------|-------------|-----------|
| Plugin marketplace | Third-party mode and extension agents | High |
| Public API + SDK gen | Let developers build on Inzyts | High |
| Embedded analytics | White-label dashboards | Medium |
| Template library | Community-contributed analysis templates per vertical | High |
| MCP server | Inzyts inside Claude Code / Desktop / Cursor / Cline | High (distribution) |
| Integration hub | Pre-built connectors (Salesforce, HubSpot, Stripe) | Medium |

### New Market Segments

| Segment | Current Fit | Adaptation Required |
|---------|-------------|---------------------|
| Healthcare analytics | Low | HIPAA / BAA, PHI handling, envelope encryption |
| Financial services | Low | SOC 2, audit retention SLA, PCI awareness |
| Education / academia | Medium | Free academic tier + collaboration |
| Startups / SMBs | High | Affordable Pro tier + low-friction onboarding |
| Enterprise | Low | SSO, multi-tenancy, SOC 2 evidence package |

### Viral / Network Effects

| Feature | Mechanism | Growth Potential |
|---------|-----------|------------------|
| Share-by-link (read-only) public dashboards | Organic discovery + branded view | High |
| Embedded "Analyzed by Inzyts" badge | Brand reach | Medium |
| Template marketplace | Community building | High |
| Referral credits | Acquisition | Medium |
| MCP placement in Claude ecosystem | Inbound from existing user base | High |

### Data Moats

| Asset | Build Path | Advantage |
|-------|-----------|-----------|
| Analysis pattern library (anonymized) | Log successful analysis patterns | Better mode suggestions |
| Vertical templates | User-contributed + curated | Industry depth |
| Error → fix corpus | Track failed-cell remediation | Self-healing system |
| Prompt A/B corpus | Measure quality per prompt variant | Continuously improving agents |
| Cross-run memory per dataset | Embed conclusions in pgvector | Compound user value over time |

---

## Perspective 6: 🔧 Data Engineer

**Focus:** Data infrastructure, pipelines, reliability, governance

### Data Pipeline & Infrastructure

| Initiative | Gap | Solution | Effort | Priority |
|------------|-----|----------|--------|----------|
| Dataset-as-object + library | Each upload re-loaded; no dedup | First-class `datasets` table; dedupe by content hash (CSV hashing exists) | M | **P0** |
| Parquet / Delta / Iceberg ingestion | Parquet via cloud only; no Delta / Iceberg | `deltalake` + `pyiceberg` adapters in `data_ingestion.py` | M | **P0** |
| Data lineage capture | None emitted | OpenLineage events from `engine.py` per agent step | M | **P1** |
| Source freshness checks | Cached profile assumes static data | Hash-poll upstream; invalidate cache on drift | S | **P1** |
| SQL agent query optimization | `SELECT *` then truncate is wasteful | Push LIMIT into prompt + `EXPLAIN`-then-confirm | M | **P1** |
| Reverse ETL | None | Push notebook conclusions → Slack / Sheets / webhook | S | **P1** (overlaps webhooks) |
| Streaming / CDC source | Batch-only | Kafka / Debezium consumer → micro-batch into Phase 1 | L | **P3** |
| Partitioned cloud reads | Whole-file reads | Range-read / column projection on Parquet | M | **P3** |
| Multi-sheet Excel support | First sheet only | Sheet picker + per-sheet ingestion | S | **P1** quick win |
| Data contracts on outputs | Informal | Publish Phase 1 profile as JSON Schema; validate consumers | M | **P2** |

### Data Quality & Observability

| Initiative | Current | Proposed | Priority |
|------------|---------|----------|----------|
| Data validation | Type detection + heuristics | Great Expectations integration, optional | **P1** |
| Quality scoring | Manual thresholds | Automated quality alerts → audit log | **P1** |
| Freshness monitoring | None | Staleness detection + alerts (per-dataset SLA) | **P2** |
| Pipeline observability | Per-job phase events | OpenTelemetry traces per agent step | **P1** |

### Governance & Compliance

| Initiative | Current | Proposed | Priority |
|------------|---------|----------|----------|
| PII detection | Regex-based, post-hoc | Presidio / spaCy NER pre-LLM masking option | **P1** |
| Data masking | At export only | At ingestion-to-LLM boundary (configurable) | **P1** |
| Audit logging | ✅ API actions | + LLM prompt/response hash logging | **P1** |
| Retention policies | Manual | Automated TTL + per-dataset retention class | **P2** |
| GDPR right-to-delete | Not implemented | DSAR endpoint + cascade-delete workflow | **P1** |
| Data catalog | Partial (data dictionary) | Metadata registry with discoverability + tags | **P2** |

### Performance & Cost

| Initiative | Current | Proposed | Priority |
|------------|---------|----------|----------|
| Result caching | Phase 1 cached | Phase 2 result cache keyed by (profile_hash, mode, question) | **P1** |
| Sampling | Fixed 10K rows for >100K | Adaptive stratified sampling (configurable per mode) | **P2** |
| Compression | None on uploads | Parquet conversion option for CSVs > 100MB | **P2** |
| Cost tracking | Per-job token count + price | Per-user / per-team rolling spend; budget enforcement | **P0** |
| Resource pooling | Per-job kernel | Warm-pool kernels with cgroup limits | **P3** |

**Data Engineer anchor initiatives (Phase 1):** Dataset-as-object + Delta/Iceberg + lineage. These convert Inzyts from "tool that runs on a CSV" into "tool that lives in a data platform."

---

## Perspective 7: 🧪 Data Scientist / ML Engineer

**Focus:** Analytics capabilities, ML features, model lifecycle, trust

### Analytics & Insight Gaps

| Capability | Use Case | Approach | Complexity | Value |
|------------|----------|----------|------------|-------|
| What-If analysis | Scenario simulation | Monte Carlo + sensitivity | M | M |
| Cohort analysis | User lifecycle | Time-based segmentation | M | H |
| Survival analysis | Time-to-event | Kaplan-Meier, Cox | M | M |
| Counterfactual explanations | "What would have changed the outcome?" | DiCE / Alibi | M | H |

### Mode Expansion

| Mode | Use Case | Approach | Complexity | Value | Phase |
|------|----------|----------|------------|-------|-------|
| Anomaly Detection (8th) | "Find weird stuff" | IsolationForest + DBSCAN outliers + LLM narration | M | H | **P2** |
| NLP / text (9th) | Free-text columns | Embeddings + BERTopic + classifier | L | H | **P3** |
| Geospatial (10th) | Geographic data | Folium / Plotly + spatial joins | L | M | parking |
| Deep Learning | Tabular DNN, image, sequence | PyTorch / Keras backends, TabNet | L | M | parking |

### Model Lifecycle (MLOps)

| Capability | Current | Proposed | Phase |
|------------|---------|----------|-------|
| Experiment tracking | None | MLflow auto-logging hooked into Phase 2 validators | **P2** |
| Model registry | None | MLflow Registry + per-tenant namespace | **P2** |
| Feature store | None | Lightweight Feast or homemade keyed table | **P3** |
| Model monitoring | None | Evidently for drift on registered models | **P3** |
| One-click serving | None | FastAPI serving endpoint per registered model + scoring API | **P3** |
| Retraining pipelines | None | Triggered by scheduler when drift threshold breached | **P3** |
| AutoML strategy backend | Manual algo selection | FLAML or AutoGluon as opt-in strategy | **P3** |

### Explainability & Trust (highest-ROI in this perspective)

| Feature | Current | Proposed | Phase |
|---------|---------|----------|-------|
| Confidence scoring on conclusions | None | Self-consistency sampling + agreement score → UI chip | **P1** |
| SHAP everywhere | Diagnostic mode only | Explainer agent runs after every Phase 2 mode | **P2** |
| Feature importance | RF only | Model-agnostic (LIME / SHAP) | **P2** |
| Bias / fairness audit | None | `fairlearn` audit when sensitive cols flagged | **P2** |
| Model cards | None | Auto-generated for each predictive run | **P3** |
| LLM call audit (prompt/response) | Cost only | Hash + retention-policied log | **P1** |

### Advanced AI Capabilities

| Capability | Current | Proposed | Phase |
|------------|---------|----------|-------|
| RAG over past runs | None | Embed conclusions + chart captions in pgvector; retrieve on similar runs | **P3** |
| Active learning from corrections | None | Capture user edits to LLM outputs; re-rank prompts | **P3** |
| Multi-LLM router | Single global LLM | Per-task routing: cheap for routing/extraction, premium for codegen | **P2** |
| Agentic debugging | Validator retry only | Dedicated debug agent with tool access | **P2** |
| Edge / ONNX export | None | Export sklearn → ONNX, ship via /predict | parking |

**DS/ML anchor initiatives:** **Confidence scoring + LLM call audit + multi-LLM router** in Phase 1–2. These are the trust + cost levers; everything else (NLP mode, MLflow, model registry) is downstream of them.

---

## Perspective 8: 🛡️ Security Engineer

**Focus:** Threat mitigation, compliance, secure development, AI/ML security

### Security Maturity Assessment

```
┌─────────────────────────────────┬─────────┬────────┬─────┐
│ Domain                          │ Current │ Target │ Gap │
├─────────────────────────────────┼─────────┼────────┼─────┤
│ Authentication & AuthZ          │   3     │   5    │  2  │  ← SSO + MFA + secrets manager
│ Application Security            │   3     │   4    │  1  │  ← SAST/DAST + dependency scan
│ Data Security                   │   2     │   4    │  2  │  ← envelope encryption + per-tenant keys
│ Infrastructure Security         │   3     │   4    │  1  │  ← gVisor / Firecracker sandbox
│ Threat Detection & Response     │   1     │   3    │  2  │  ← SIEM + alert rules + IR playbooks
│ Compliance & Governance        │   1     │   3    │  2  │  ← SOC 2 Type 1 evidence
│ Secure Development Lifecycle    │   2     │   4    │  2  │  ← threat modeling, security training
│ AI/ML Security                  │   3     │   4    │  1  │  ← LLM output validation + injection corpus
└─────────────────────────────────┴─────────┴────────┴─────┘
```

### Top Security Initiatives (next 12 months)

| Initiative | Threat | Severity | Compliance | Cx | Priority |
|------------|--------|----------|------------|----|----------|
| SSO (OIDC / SAML) + MFA enforcement | Account takeover, weak passwords | High | SOC 2 / ISO 27001 | M | **P0** |
| Secrets manager integration (Vault / AWS SM) | `.env` proliferation; JWT secret in plaintext | Med | SOC 2 | M | **P0** |
| SAST (Semgrep) + dependency scan in CI | Supply chain | Med | SOC 2 | S | **P0** quick win |
| Cost budgets per user (already in PM list) | Cost-explosion via prompt abuse | High | — | S | **P0** |
| Prompt injection regression corpus | Indirect injection escalation | High | — | S | **P0** |
| LLM output validation layer | Code/SQL injection via data | High | — | M | **P0** |
| LLM call audit log (prompt/response hash) | Trace AI decisions for compliance | Med | SOC 2 | S | **P1** |
| Per-tenant envelope encryption for uploads | Cross-tenant data leak | High | GDPR | M | **P1** |
| TLS 1.3 enforcement | MITM | High | PCI-DSS | S | **P1** |
| DAST against staging (OWASP ZAP) weekly | Injection / auth bypass regressions | Med | SOC 2 | S | **P1** |
| Centralized SIEM (Loki+Grafana or Datadog) | Detection gap | High | SOC 2 | M | **P1** |
| Postgres row-level security on jobs/notebooks/datasets | AuthZ bypass | Med | GDPR | M | **P1** |
| Sandbox upgrade to gVisor / Firecracker | LLM-generated code escape | High | — | L | **P2** |
| Threat model (STRIDE) per new feature in PR template | Unmodeled risk | Med | SOC 2 | S | **P1** |
| GDPR DSAR endpoints (delete + export) | Subject rights | High | GDPR | M | **P1** |
| Bug bounty / responsible disclosure | Unknown vulns | Med | — | S | **P2** |
| Penetration test (external) | Unknown vulns | High | SOC 2 | External | **P2** |
| SOC 2 Type 1 audit | Procurement gating | High | SOC 2 | External | **P2** |

### AI/ML Security (Inzyts-specific)

| Initiative | Threat | Mitigation | Priority |
|------------|--------|------------|----------|
| Prompt injection corpus in `tests/security/` | Known-bad inputs as regression tests | PromptInjection-Bench harness | **P0** |
| LLM output schema + denylist | Malicious code/SQL emitted | Pydantic + regex denylist on agent outputs | **P0** |
| Sandbox escape adversarial CI test | Bypass via `import os`, file write, network | Add expected-fail test to CI | **P0** |
| Agent action allowlist | Rogue tool use | Per-agent tool capability declaration | **P1** |
| LLM prompt/response retention | Auditability of AI decisions | Hash + retention class | **P1** |
| Model extraction protection (when serving) | Stealing trained models | Rate limit + watermarking | **P3** |

### Compliance Roadmap

| Framework | Current | Required Actions | Target |
|-----------|---------|------------------|--------|
| **SOC 2 Type 1** | Controls partial | SSO, secrets manager, SIEM, SDL/SAST, IR playbook | End of Phase 2 (~6mo) |
| **SOC 2 Type II** | Not started | 6-month evidence period after Type 1 | End of Phase 3 (~12mo) |
| **GDPR** | Partial (audit + RBAC + per-job ownership) | DSAR endpoints, masking-at-LLM-boundary, retention policy | End of Phase 1 |
| **HIPAA** | Not started | BAA, envelope encryption, PHI handling, audit retention SLA | Defer to demand |
| **ISO 27001** | Not started | ISMS, risk register, policies | Phase 3+ |

### Security Gates Between Phases

| Gate | Required before proceeding |
|------|----------------------------|
| **P1 → P2** | SAST + dep-scan green; prompt-injection regression suite green; cost budgets enforced; LLM output validation live; sandbox-escape adversarial test green |
| **P2 → P3** | SSO live; secrets manager replacing `.env`; RLS on jobs/notebooks/datasets; OTEL tracing in prod; SIEM operational |
| **Exit P3** | SOC 2 Type 1 audit started; sandbox hardened (gVisor/Firecracker); lineage capture on >90% of runs; incident response tested |

---

## Unified 12-Month Plan

Three rolling phases of ~3–4 months. Each item has an owner perspective (🎯 PM, 🎨 UX, 🏗️ Arch, 👤 User, 🚀 Growth, 🔧 Data, 🧪 ML, 🛡️ Security).

### Phase 1 — Trust & Quick Wins (months 0–3)
**Theme:** Stop the bleed; ship the perception/safety wins; preserve cache on bigger work.

| Initiative | Owner | Pri | Effort |
|------------|-------|-----|--------|
| SSE-streamed agent reasoning | 🎨 🏗️ | P0 | S |
| Cost budgets per user/team (default-on) | 🎯 🛡️ | P0 | S |
| Confidence scoring on conclusions (chip + tooltip) | 🧪 👤 | P0 | M |
| Dataset-as-object + library (dedup by hash) | 🔧 | P0 | M |
| MCP server exposing Inzyts | 🚀 | P0 | S |
| LLM output validation layer | 🛡️ 🧪 | P0 | M |
| Prompt-injection regression corpus | 🛡️ 🧪 | P0 | S |
| SAST (Semgrep) + dep-scan in CI | 🛡️ | P0 | S |
| Webhook notifications (Slack / Teams / HTTP) | 🎯 | P1 | S |
| Word (.docx) + Notebook → Python script export | 🎯 | P1 | S |
| Cmd-K command palette | 🎨 | P1 | M |
| Demo dataset gallery + onboarding tour | 🎨 | P1 | S |
| Multi-sheet Excel ingestion | 🔧 | P1 | S |
| LLM call audit log (prompt/response hash) | 🛡️ 🧪 | P1 | S |
| Result cache on Phase 2 (profile_hash + mode + question) | 🔧 | P1 | M |
| Sandbox escape adversarial CI test | 🛡️ | P0 | S |
| Threat-model section in PR template | 🛡️ | P1 | S |

**Phase 1 success criteria:**
- Median perceived time-to-first-output < 30s (via SSE).
- 0 cost-overrun incidents post-budget rollout.
- Confidence chip visible on ≥90% of conclusions.
- MCP server has ≥200 active sessions/mo.
- All P0 security items shipped; SAST + dep-scan green in CI.

### Phase 2 — Sellability (months 3–6)
**Theme:** Make it Team-tier sellable; pass the procurement filter.

| Initiative | Owner | Pri | Effort |
|------------|-------|-----|--------|
| Dashboard builder (pinned cells → widgets) | 🎯 🎨 | P0 | L |
| Team workspaces + role-based sharing | 🎯 🛡️ | P0 | L |
| Share-by-link (read-only public/private) | 🎯 | P0 | M |
| SSO (OIDC + SAML via WorkOS / Authentik) + MFA | 🛡️ 🎯 | P0 | M |
| Secrets manager integration (Vault / AWS SM) | 🛡️ 🏗️ | P0 | M |
| MLflow auto-logging on Phase 2 validators | 🧪 | P1 | M |
| Anomaly detection mode (8th) | 🧪 | P1 | M |
| OpenTelemetry tracing across all agents | 🏗️ | P1 | M |
| Versioned handoff schemas (`v1`, `v2`) | 🏗️ | P1 | M |
| Postgres RLS on jobs / notebooks / datasets | 🛡️ 🏗️ | P1 | M |
| GDPR DSAR endpoints (delete + export) | 🛡️ | P1 | M |
| SHAP-everywhere explainer agent | 🧪 | P1 | M |
| Multi-LLM router with per-task model | 🧪 🏗️ | P1 | M |
| TLS 1.3 enforcement + DAST weekly | 🛡️ | P1 | S |
| SIEM (Loki + Grafana or Datadog) | 🛡️ | P1 | M |
| Pre-LLM PII masking option (Presidio) | 🔧 🛡️ | P1 | M |
| Run history with diff view | 👤 🎯 | P1 | M |
| Scheduled runs (cron) | 👤 🎯 | P1 | M |
| Agentic debugging | 🧪 🚀 | P2 | M |

**Phase 2 success criteria:**
- ≥10 design-partner orgs on Team tier.
- ≥50 active team workspaces.
- SSO unblocks ≥5 enterprise prospects.
- SOC 2 Type 1 audit prep started; ≥80% controls have evidence.
- DSAR endpoints live; pre-LLM PII masking opt-in available.

### Phase 3 — Leverage & Platform (months 6–12)
**Theme:** Turn the 27-agent system into a platform; place inside ecosystems; certify.

| Initiative | Owner | Pri | Effort |
|------------|-------|-----|--------|
| Plugin / agent SDK (manifests + capability decls) | 🏗️ 🚀 | P0 | L |
| NLP / text mode (9th) | 🧪 | P1 | L |
| RAG over past runs (cross-run memory in pgvector) | 🧪 🚀 | P1 | M |
| OpenLineage emission per agent step | 🔧 | P1 | M |
| Delta / Iceberg ingestion adapters | 🔧 | P1 | M |
| Sandbox upgrade to gVisor / Firecracker | 🛡️ 🏗️ | P1 | L |
| SOC 2 Type 1 audit (external) | 🛡️ 🎯 | P1 | External |
| Fairness / bias audit module | 🧪 🛡️ | P2 | M |
| Embedded mode (white-label widget + JWT exchange) | 🚀 | P1 | M |
| Model registry + serving (MLflow + FastAPI scoring) | 🧪 🏗️ | P2 | L |
| Worker autoscaling (Celery → KEDA) | 🏗️ | P2 | M |
| Plugin marketplace (browse / install / submit) | 🚀 | P2 | L |
| Reverse ETL (push conclusions to webhooks/Sheets) | 🔧 | P2 | S |
| API v3 with deprecation contract | 🏗️ | P2 | M |
| Compliance dashboard (SOC 2 / GDPR / HIPAA evidence) | 🛡️ | P2 | M |
| Custom agent prompt overrides | 👤 | P3 | S |
| SOC 2 Type II evidence period started | 🛡️ | P2 | External |

**Phase 3 success criteria:**
- ≥5 third-party plugins published.
- ≥1 named placement in Anthropic / IDE ecosystem (MCP-driven).
- SOC 2 Type 1 certified.
- Sandbox running on gVisor/Firecracker in prod.
- Lineage emission on ≥90% of runs.

---

## Dependencies, Gates, Risks, Metrics

### Cross-Perspective Dependency Chain

```
🛡️ SSO + Secrets Mgr ──► 🏗️ RLS + Versioned Schemas ──► 🎯 Workspaces ──► 🎯 Dashboards
        │                                                                         │
        └──► 🛡️ SIEM ──► 🛡️ SOC 2 Type 1 audit ◄───────── Enterprise sale ────────┘

🏗️ Plugin SDK ──► 🧪 NLP / Anomaly modes ──► 🚀 Agent marketplace
🔧 Dataset-as-object ──► 🔧 Lineage ──► 🧪 RAG over past runs ──► 🚀 Cross-run memory
🎨 SSE streaming + 🧪 Confidence scoring  ──► 👤 Trust  ──► 🎯 Conversion
🛡️ LLM output validation ──► 🛡️ Sandbox escape test ──► 🛡️ gVisor sandbox ──► HIPAA option
```

### Top Risks per Phase

| Phase | Risk | Likelihood | Impact | Mitigation |
|-------|------|------------|--------|------------|
| P1 | SSE refactor regresses progress events | Med | Med | Contract tests on `progress_tracker`; feature flag |
| P1 | Dataset dedup migration loses upload references | Med | High | Dual-write window + content-hash backfill |
| P1 | MCP server exposes unauthenticated path | Med | High | Same JWT gating as REST; CI test for unauth |
| P1 | LLM output validation breaks existing agents | Med | Med | Schema versioned; opt-in per-agent; canary |
| P2 | Dashboard scope creep ("just like Tableau") | High | Med | MVP = pin existing cells; explicit non-goals |
| P2 | SSO admin lockout | Med | High | Local-auth fallback for at least 1 admin |
| P2 | MLflow disk growth | Med | Med | Retention policy from day 1 |
| P2 | Pre-LLM PII masking degrades analysis quality | Med | Med | Opt-in; per-column control; A/B against unmasked |
| P3 | Plugin SDK ABI break | High | High | Version handoffs first; schemas before plugins |
| P3 | gVisor perf regression on Phase 2 | Med | Med | Benchmark suite; flag-flip per environment |
| P3 | SOC 2 evidence collection chews engineer time | High | Med | Start trail capture in P2 (passive logging) |

### KPIs by Phase

| Phase | Metric | Target |
|-------|--------|--------|
| P1 | Time-to-first-output (perceived) | < 30s |
| P1 | Cost-overrun incidents | 0 |
| P1 | Confidence chip coverage | ≥90% of conclusions |
| P1 | MCP active sessions / mo | 200+ |
| P1 | P0 security items shipped | 100% |
| P2 | Team-tier design partners | 10+ |
| P2 | Active team workspaces | 50+ |
| P2 | Dashboard creations / mo | 100+ |
| P2 | SSO-unblocked enterprise prospects | 5+ |
| P2 | DSAR turnaround SLA | <30 days |
| P3 | 3rd-party plugins published | 5+ |
| P3 | RAG-augmented runs / mo | 500+ |
| P3 | Lineage coverage | ≥90% of runs |
| P3 | SOC 2 Type 1 controls evidenced | ≥80% |

### Resource Implications

| Phase | Engineering FTEs | Skills Needed |
|-------|------------------|---------------|
| P1 | 3 | Backend (Python/FastAPI), Frontend (React/SSE), Security generalist |
| P2 | 4–5 | + Frontend-heavy (dashboards/workspaces), DS/ML (confidence + SHAP), Part-time IT/SecOps for SSO + SOC 2 |
| P3 | 5–6 | + Distributed systems (plugin SDK, gVisor), MLOps (registry/serving), DevRel (plugins + MCP ecosystem) |

### Threat Model Summary (Top Threats per Phase)

| Phase | Top Threat | Vector | Priority Control |
|-------|-----------|--------|------------------|
| P1 | Prompt injection escalation | Malicious data → agent tool abuse | Output validation + injection corpus |
| P1 | Cost explosion | LLM abuse via prompt loops | Per-user budgets |
| P1 | Cross-tenant leak via dataset dedup | Hash collision / weak keying | Per-user namespace + content-hash + ACL |
| P2 | Workspace privilege escalation | Misconfigured share | RLS + share-link scopes + audit |
| P2 | SSO IdP misconfiguration | Wrong claim mapping | Test suite per IdP; staged rollout |
| P3 | Sandbox escape via novel exploit | LLM-generated payload | gVisor / Firecracker + adversarial CI |
| P3 | Plugin supply-chain attack | Malicious 3rd-party plugin | Signed manifests + capability allowlist + review |

---

## Parking Lot

Items considered but explicitly deferred beyond the 12-month horizon. Re-evaluate at next refresh.

| Item | Why deferred |
|------|--------------|
| Streaming / CDC ingestion (Kafka, Debezium) | Niche until enterprise volume; batch + dataset-as-object covers 95% |
| Geospatial mode (10th) | Large effort, ~2K reach; defer until vertical demand surfaces |
| Deep Learning mode | Distinct skill set; FLAML via AutoML is cheaper first step |
| Voice-first follow-up (Whisper STT/TTS) | Differentiator score 3/5; revisit after MCP traction |
| Edge / ONNX export | Niche; defer until model-serving demand exists |
| HIPAA / PCI compliance | Demand-driven; only after 1+ paying healthcare/fin customer |
| Active learning from corrections | Requires sustained user-correction telemetry; defer until P3 baseline established |
| Multi-tenancy with hard isolation | RLS in P2 covers most cases; full schema-per-tenant only if enterprise procurement requires |

---

## Appendix: Perspective Interaction Map

```
                         ┌─────────────┐
                         │  🎯 Product │
                         │   Manager   │
                         └──────┬──────┘
                                │ defines value
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
         ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
         │  🎨 UI/UX   │ │  👤 User    │ │  🚀 Growth  │
         │  Designer   │ │  Feedback   │ │  Strategy   │
         └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
                │               │               │
                └───────────────┼───────────────┘
                                │ shapes requirements
                                ▼
                    ┌───────────────────────┐
                    │    🏗️ Software        │
                    │     Architect         │
                    └───────────┬───────────┘
                                │ designs systems
           ┌────────────────────┼────────────────────┐
           ▼                    ▼                    ▼
    ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
    │  🔧 Data    │◄────►│  🧪 Data    │◄────►│  🛡️ Security│
    │  Engineer   │      │  Scientist  │      │  Engineer   │
    └──────┬──────┘      └──────┬──────┘      └──────┬──────┘
           │                    │                    │
           │  enables           │ enables            │ secures
           │                    │                    │
           └────────────────────┼────────────────────┘
                                │ delivers secure capabilities
                                ▼
                         ┌─────────────┐
                         │  🎯 Product │
                         │   Value     │
                         └─────────────┘
```

### Security Touchpoints

```
🛡️ Security Engineer interfaces with:
├── 🎯 Product Manager    → Security as feature (SSO, audit, compliance badges, cost budgets)
├── 🎨 UI/UX Designer     → Secure UX (auth flows, error sanitization, PII handling, confidence chip)
├── 🏗️ Software Architect → Threat modeling, RLS, sandbox, secrets manager
├── 🔧 Data Engineer      → Encryption, access control, audit logging, lineage
├── 🧪 Data Scientist     → ML security (prompt injection, output validation, model protection)
└── 🚀 Growth Strategist  → Security as differentiator (enterprise readiness, MCP gating)
```

---

## Conclusion

Inzyts has done the hard work of becoming a credible *individual* analysis tool: 27 agents, 7 modes, multi-source ingestion, hardened auth, hardened sandbox, full report stack. The next 12 months are about making it **trustworthy at team scale (Phase 1)**, **sellable to teams (Phase 2)**, and **leveraged as a platform (Phase 3)**.

Three commitments dominate:

1. **Trust** — SSE streaming + confidence scoring + cost budgets in Phase 1.
2. **Sellability** — Dashboards + workspaces + SSO in Phase 2.
3. **Leverage** — Plugin SDK + MCP + dataset-as-object + RAG over past runs across Phase 1 → 3.

Strategic differentiators to maintain throughout:

- **27-agent autonomous system** — unique in the market.
- **Profile lock anti-hallucination** — trust and reliability.
- **7+ mode pipeline** — comprehensive coverage, growing to 9+.
- **Self-correcting validation loops** — quality assurance built-in.
- **Smart caching + cost tracking** — efficiency.
- **Conversational follow-up + cell-level editing** — interactive analysis surface.
- **Multi-source ingestion** — CSV / SQL / cloud DWH / object storage / REST.
- **Hardened security posture** — JWT + RBAC + audit + sandbox + Docker isolation.

Re-evaluate this roadmap quarterly. Drop items the moment evidence says they aren't load-bearing.

---

**Document Version**: 6.0.0
**Last Updated**: 2026-04-28
**Supersedes**: v5.0.0 (2026-03-10)
**Status**: Approved for Implementation
