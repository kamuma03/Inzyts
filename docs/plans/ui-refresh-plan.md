# Feature Plan: Inzyts UI Refresh — Command Center + Mode Selector C

**Date**: 2026-04-27
**Project**: Inzyts (`/home/mukan/Documents/Inzyts`)
**Status**: Planning — approved for implementation
**Source spec**: `HANDOFF.md` (design-approved)
**Reference design**: `Inzyts redesign explorations.html` — artboards "V1 refined — default" and "Mode selector C · refined"

---

## 1. Overview

### Goal
Replace the current job/workspace surface with an analyst-tuned **Command Center** that surfaces live pipeline state (per-agent), a clickable column inspector, tabbed visual/code/data/logs preview, and run-vs-run KPI deltas. In parallel, replace the LLM-backed mode-suggestion call with a deterministic local keyword heuristic — same hook signature, no network round-trip on keystroke.

When this is done, an analyst opening a job sees: which agent is talking, how this run compares to the last one, the column distribution they need, and the streaming Python they're about to run — without clicking through tabs or panels.

### Scope

**In scope:**
- Replace `JobDetailsPage` rendering with a new `CommandCenterView` (gated behind `VITE_FEATURE_COMMAND_CENTER`).
- New left rail (`PipelineRail`) showing the actual 2-phase workflow with sub-steps and 22 real agents.
- New right rail (`ColumnInspector`) replacing the static `ContextPanel` for active jobs.
- New center stack (`PreviewTabs`: Visual / Code / Data / Logs).
- New top strip (`TopStrip`) with KPI deltas vs. previous job.
- New status bar (retries, cache hits, keyboard shortcuts — **no kernel state in V1**).
- Backend additions: `metrics_snapshot` / `phase_update` WS events; `GET /jobs/{id}/columns`; `GET /jobs/{id}/cost` with per-phase aggregation; `csv_hash` column on Job + previous-job lookup query.
- Mode Selector C: local keyword heuristic in `frontend/src/utils/modeHeuristic.ts`, wired through the existing `useModeSuggestion` hook with the same return shape. Existing `ModeSelector` UI gains matched-keyword display, confidence dot, and a "Why?" tooltip.
- Vitest tests for the heuristic; React Testing Library tests for new hooks where practical.

**Out of scope (V1):**
- Kernel/sandbox state in StatusBar (no `KernelState` endpoint or `useKernelState` hook). Status bar shows retries, cache hits, and shortcut hints only.
- Command palette (⌘K) — keyboard hotkey focuses search input only.
- Cell-level accept/edit/regenerate inside the Code tab (that is V3, separate roadmap item).
- "Ask Inzyts" slide-over (V2 conversational entry — separate roadmap).
- Executive Brief share view (V4 — separate roadmap).
- Mobile / responsive layout.
- Real-time multi-user presence.

---

## 2. Requirements

| #   | Requirement | Acceptance criterion |
|-----|-------------|----------------------|
| R1  | Mode-suggestion in the question box never makes a network call. | `wireshark`/network panel shows zero outbound requests on keystroke; `useModeSuggestion` no longer references `AnalysisAPI.suggestMode`. |
| R2  | The suggestion chip appears within 300ms of the user pausing typing. | Manual: type, pause; chip is visible in <400ms. Vitest perf assertion: 1000 calls <50ms. |
| R3  | The chip never replaces the user's selected mode without an explicit Apply click. | Selecting mode X, then typing keywords for mode Y, leaves the active mode = X until Apply pressed. |
| R4  | When the heuristic confidence is below `MIN_CONFIDENCE` (0.4), no chip is shown. | `suggestMode("this is just a sentence", noCtx)` returns `null`. |
| R5  | All 7 modes remain selectable from the grid at all times. | Grid is always rendered (no auto-hide when chip shown). Keyboard arrows + 1–7 hotkeys still navigate the grid. |
| R6  | When the Command Center feature flag is on, opening a running job renders the new layout within 1s of WS connect. | E2E test: load `/jobs/:id`, assert `CommandCenterView` mounted and `PipelineRail` shows ≥1 phase block in <1s. |
| R7  | When the feature flag is off, `JobDetailsPage` renders the legacy AgentTrace + tabs unchanged. | Toggle env, reload, observe legacy view; no regressions on completed/failed jobs. |
| R8  | KPI deltas in `TopStrip` only render when a previous comparable job exists. | API returns `previous_job_id != null` only when a job exists with same `(user_id, mode, csv_hash)`; chips hidden otherwise. |
| R9  | Clicking a column in `ColumnInspector` updates the detail card in <50ms with no network call. | Performance API: time from click to detail render <50ms; network panel shows no fetch. |
| R10 | Switching tabs in `PreviewTabs` preserves scroll position per tab. | Scroll Visual to bottom, switch to Code, switch back — Visual still at bottom. |
| R11 | The Code tab streams Python cell-by-cell from the active codegen agent. | While codegen agent is running, new content appears in the Code tab as agent events arrive; stream pill shows "● streaming" → "● ready" on phase done. |
| R12 | `PipelineRail` shows all 5 sub-steps even when some are skipped (e.g. exploratory mode), greying out the inactive ones. | In exploratory mode, Strategy and Extensions sub-steps render with `--text-dim` color and "skipped" badge; the active sub-steps render at full opacity. |
| R13 | Status bar updates retries/cache-hits at least every 2s while a job runs. | Manual: observe ticker advancing while job runs. |
| R14 | Bundle size delta from the change is ≤ +30KB gzipped. | `vite build` output diff before/after; CI script asserts the budget. |
| R15 | Lighthouse a11y score on the Command Center is ≥ 95; every interactive element keyboard-reachable; existing focus-ring preserved. | `npx lighthouse <url> --only-categories=accessibility` ≥ 95. Tab through every control with no mouse. |
| R16 | Cost breakdown surfaces phase-level costs (not only total). | `GET /jobs/{id}/cost` returns ≥2 rows for any completed job; CostBreakdown panel renders per-phase rows. |
| R17 | Per-job `csv_hash` is computed and persisted on job creation; previous-job lookup uses it. | DB row has non-null `csv_hash` after job creation; lookup query returns matching prior job for the same user+mode+hash. |

---

## 3. Impact Analysis

### 3.1 Architecture — **Medium**
- New frontend module: `frontend/src/components/command-center/` (12+ components + `primitives/`).
- New backend aggregator that rolls per-agent events into `metrics_snapshot` and `phase_update` payloads at ~500ms cadence — sits alongside the existing `useSocket` event broadcaster in `src/server/routes/websockets.py`.
- Existing token-cost aggregation moves from job-total to per-phase grain (additive — keeps the job-level total).
- No changes to LangGraph workflow ([src/workflow/graph.py](../../src/workflow/graph.py)) or agent factory ([src/workflow/agent_factory.py](../../src/workflow/agent_factory.py)).
- Compliance: matches the existing pattern (FastAPI routes under `src/server/routes/`, React feature components under `frontend/src/components/`). No deviations.

### 3.2 UI / UX — **High**
- The `JobDetailsPage` outlet is fully replaced when the flag is on. Sidebar + global header are untouched.
- New visual language: 13px base body, 10px metadata, JetBrains Mono for numbers/IDs/agent names.
- Density tightened ~15% vs current.
- Net new affordances: clickable column rows, tabs, KPI delta chips, agent status dots, sparklines.

### 3.3 Frontend — **High**
- New directory tree under [frontend/src/components/command-center/](../../frontend/src/components/command-center/) (does not exist yet).
- New hooks: `useRunMetrics`, `usePhases`, `useColumnProfile`, `useKeyboardShortcuts`. (`useDataProfile` and `useKernelState` from spec are NOT created — `useDataProfile` is folded into `useColumnProfile`; `useKernelState` is dropped per scope decision.)
- Existing `AgentTrace.tsx` becomes dead code when flag is on; deprecate but keep file until flag is removed.
- New API types in [frontend/src/api.ts](../../frontend/src/api.ts): `RunMetrics`, `PhaseStatus`, `SubStepStatus`, `ColumnProfile`, `CostBreakdown`. **No `KernelState` type in V1.**
- Bundle size: target ≤ +30KB gzipped. Pure SVG primitives — no chart library.
- No new client-side runtime dependencies (react-window already installed at 2.2.7).

### 3.4 Backend — **Medium**
- New WS events emitted by [src/server/routes/websockets.py](../../src/server/routes/websockets.py): `metrics_snapshot` (every 500ms during run), `phase_update` (on any phase state change). Existing `log` / `progress` / `agent_event` events kept as-is.
- New REST endpoints in [src/server/routes/jobs.py](../../src/server/routes/jobs.py):
  - `GET /jobs/{job_id}/columns` → `ColumnProfile[]` (rolled up from `DataProfilerAgent` output, which already produces this — see [src/agents/phase1/data_profiler.py](../../src/agents/phase1/data_profiler.py)).
  - `GET /jobs/{job_id}/cost` → `CostBreakdown[]` with per-phase rows.
- Token tracking change: per-phase rollup added to the cost aggregator (currently only emits a flat `cost_estimate` JSON on the Job model — [src/server/db/models.py:68-70](../../src/server/db/models.py#L68-L70)). Add a sibling `cost_breakdown` JSON column or extend the existing JSON shape.
- Previous-job lookup: new query `find_previous_job(user_id, mode, csv_hash)` returning the most recent completed job matching the tuple.
- No KernelState endpoint in V1.

### 3.5 Data — **Low**
- New column on `Job` table: `csv_hash` (varchar, sha256 of the input CSV bytes, nullable for legacy rows).
- Optional new column: `cost_breakdown` (JSON) if extending the existing `cost_estimate` field is awkward.
- Migration strategy: additive only. Legacy rows have `csv_hash = NULL`; previous-job lookup excludes nulls — no backfill required for V1 (deltas just won't render for jobs created before the migration; new jobs will populate).
- No retention or volume change.

### 3.6 Security — **Low**
- All new endpoints inherit Bearer-token auth from the existing `jobs.py` router.
- No new file-upload or input-deserialization surface.
- WebSocket auth unchanged — uses the same token validation as today.
- Frontend continues to keep the API token in `sessionStorage` only (memory note: never `localStorage` / `VITE_API_TOKEN`).
- No new PII path — `ColumnProfile` includes a `pii` role chip but the data was already being computed by `DataProfilerAgent`; we're only re-exposing it.

### 3.7 Safety (AI/ML) — **N/A**
- No model-behaviour change. Mode Selector C *removes* an LLM call — strict reduction in model surface area, lower risk of prompt injection and hallucinated mode suggestions.
- Considered: heuristic could miss edge phrasings the LLM caught. Mitigation: chip is suggestion-only, never auto-applies — the user always confirms.

### 3.8 Performance — **Medium**
- `metrics_snapshot` arrives every 500ms during a run. `TopStrip` and `PipelineRail` must render in <16ms per push.
  - Mitigation: `React.memo` on `KpiCell`, `PhaseBlock`, `SubStepRow`, and `AgentRow`. Stable keys derived from `agent.name`. Pass primitives, not new objects, where possible.
- `EventStream` virtualization: react-window when entries > 500 (`useSocket` already caps logs at 500 — see [frontend/src/hooks/useSocket.ts:99](../../frontend/src/hooks/useSocket.ts#L99) — but new `agent_event` rate may push beyond that).
- `ColumnList` not virtualized (datasets cap at ~50 columns in practice).
- Heuristic perf: 1000 calls <50ms (Vitest assertion). Effectively free.

### 3.9 Testing — **Medium**
- New unit tests:
  - [frontend/src/utils/modeHeuristic.test.ts](../../frontend/src/utils/modeHeuristic.test.ts) — coverage of every mode + null cases + perf smoke (per spec §2.5).
  - [frontend/src/utils/formatters.test.ts](../../frontend/src/utils/formatters.test.ts) — `formatDelta`, `formatCost`.
- New component tests (React Testing Library):
  - `ColumnInspector` selection updates `ColumnDetailCard` synchronously.
  - `PreviewTabs` preserves scroll per tab.
  - `TopStrip` hides delta chips when `previous_job_id` is null.
- New backend tests:
  - `tests/server/test_jobs_endpoints.py` for the 2 new routes.
  - `tests/workflow/test_cost_aggregator.py` for per-phase cost rollup.
  - `tests/server/test_previous_job_lookup.py` for the dedup query.
- E2E: extend any existing flows to load a job under the feature flag and assert layout + tab behaviour. (Memory mentions Vitest is configured at `frontend/vitest.config.ts`. No Playwright/Cypress today — manual smoke for now, captured in §8.)

### 3.10 Dependencies & licensing — **Low**
- No new heavyweight deps. All primitives are inline SVG.
- JetBrains Mono added via Google Fonts `<link>` in [frontend/index.html](../../frontend/index.html) — Apache 2.0, compatible with the project.
- `react-window` already installed at 2.2.7 — used for `EventStream` virtualization.

### 3.11 DevOps & deployment — **Low**
- One new env var: `VITE_FEATURE_COMMAND_CENTER` (boolean, defaults to `false` → legacy view).
- Two new WS event types — backwards compatible because old clients ignore unknown event types.
- DB migration: one new column on `Job` (Alembic — confirm migration tooling).
- No new infrastructure.
- Rollback: flip the env var; on re-deploy, legacy `JobDetailsPage` rendering is restored. DB column stays; that's fine because it's additive.

### 3.12 Risk — **Medium overall**
- Highest risk: WS aggregator load + render budget at 500ms cadence with 22 agents. Mitigated by memoization + perf testing.
- Second risk: per-phase cost aggregation correctness (token-tracking is the primary pricing input for the project). Mitigated by parallel old/new emission during Phase 1 of rollout.
- Reversibility: high — feature flag flip restores legacy view in <1 minute.

### Impact Summary

| Dimension | Impact level | Key concern |
|-----------|--------------|-------------|
| Architecture | Medium | New CC module + WS aggregator + cost rollup |
| UI / UX | High | Replaces JobDetailsPage rendering (gated) |
| Frontend | High | 12+ new components, 4 new hooks, new types |
| Backend | Medium | 2 new REST routes, 2 new WS events, csv_hash column, previous-job query |
| Data | Low | Additive `csv_hash` column; no breaking change |
| Security | Low | Inherits existing auth; reduces LLM surface |
| Safety | N/A | Removes an LLM call |
| Performance | Medium | 500ms metrics push + render budget |
| Testing | Medium | Heuristic + hook + endpoint tests |
| Dependencies | Low | JetBrains Mono only; no JS deps |
| DevOps | Low | One env var + one migration |
| Risk | Medium | Behind flag → low effective risk |

---

## 4. Implementation Plan

### Approach
Land the work in three vertical slices, each shippable behind the same feature flag. Within each slice, build the backend contract first so the frontend can consume real data from day one (avoid mock-driven divergence — memory note: integration tests must hit real services, not mocks).

**Order is driven by analyst value per unit work.** The Column Inspector is the biggest analyst-quality win (per spec §4.4) and `DataProfilerAgent` already computes everything needed, so it goes first.

### Phases

**Phase A — Foundation (3–4 days)**
- Mode Selector C heuristic shipped end-to-end (small, isolated, reversible — even without the flag).
- Backend contract additions: `csv_hash` column, previous-job lookup, per-phase cost aggregation, new REST routes, new WS events.
- Frontend foundation: CSS role tokens, JetBrains Mono import, feature flag wiring, new API types in `api.ts`.

**Phase B — Command Center vertical (5–7 days)**
- `CommandCenterView` shell + `MainGrid` + `TopStrip` (KPI deltas).
- `PipelineRail` showing the 2 phases with their sub-steps and 22 agents.
- `ColumnInspector` + `ColumnDetailCard` + `CostBreakdown` panel.
- Behind-flag rollout to internal users.

**Phase C — Polish (3–5 days)**
- `PreviewTabs` (Visual / Code / Data / Logs) with scroll preservation.
- `EventStream` (port of legacy logs panel + filters; virtualized when >500).
- `StatusBar` (retries, cache hits, kbd hints — no kernel state).
- Keyboard shortcuts hook (`useKeyboardShortcuts`).
- A11y pass, perf pass, bundle budget verification.

---

## 5. Task Breakdown

### Phase A — Foundation

| # | Task | Layer | Depends on | Est. complexity |
|---|------|-------|------------|-----------------|
| A1 | Add CSS role tokens (`--bg-surface-hi`, `--text-dim`, `--accent-violet`, `--status-good/warn/bad`) to [frontend/src/index.css](../../frontend/src/index.css). | Frontend | — | Low |
| A2 | Import JetBrains Mono via `<link>` in [frontend/index.html](../../frontend/index.html). | Frontend | — | Low |
| A3 | Add `VITE_FEATURE_COMMAND_CENTER` env var with a one-line boolean read in a new [frontend/src/featureFlags.ts](../../frontend/src/featureFlags.ts). | Frontend | — | Low |
| A4 | Create `frontend/src/utils/modeHeuristic.ts` with `suggestMode(question, ctx)` per spec §2.2. | Frontend | — | Low |
| A5 | Rewrite `frontend/src/hooks/useModeSuggestion.ts` to call the heuristic instead of `AnalysisAPI.suggestMode`. Same return shape. Drop the LLM API method (or mark deprecated if used elsewhere). | Frontend | A4 | Low |
| A6 | Update `frontend/src/components/ModeSelector.tsx`: matched-keywords text, confidence dot (green ≥0.7, amber ≥0.5, gray <0.5), "Why?" tooltip. Confirm Apply still requires explicit click. Keep grid always visible. | Frontend | A5 | Low |
| A7 | Tests: `frontend/src/utils/modeHeuristic.test.ts` — every mode, ctx bias, null cases, perf smoke (per spec §2.5). | Frontend tests | A4 | Low |
| A8 | Add `csv_hash` column to `Job` model ([src/server/db/models.py](../../src/server/db/models.py)) + Alembic migration. Compute hash on job creation in the analyze endpoint. | Backend / Data | — | Low |
| A9 | Add `find_previous_job(user_id, mode, csv_hash)` query helper. Returns most recent completed prior job, or None. | Backend | A8 | Low |
| A10 | Per-phase cost aggregation: extend the token tracker to bucket cost by phase id (`phase1` / `phase2` / `extensions`), and emit a `cost_breakdown` (list of `{phase, cost_usd, is_estimate}`) alongside the existing `cost_estimate`. | Backend | — | Medium |
| A11 | New REST: `GET /jobs/{job_id}/columns` returning `ColumnProfile[]` from the locked `DataProfilerAgent` handoff. | Backend | — | Low |
| A12 | New REST: `GET /jobs/{job_id}/cost` returning `CostBreakdown[]`. | Backend | A10 | Low |
| A13 | New WS event: `metrics_snapshot` — emit `RunMetrics` every 500ms during a run. Aggregator computes `agents_active` / `agents_total` (=22, dynamic) / token totals / cost / quality / elapsed / eta from existing per-agent events + `find_previous_job` for `previous_*`. | Backend | A9, A10 | Medium |
| A14 | New WS event: `phase_update` — emit on any phase or sub-step state change. Payload is full `PhaseStatus[]` (2 entries: phase 1, phase 2; each with `steps[]`). | Backend | — | Medium |
| A15 | New API types in [frontend/src/api.ts](../../frontend/src/api.ts): `RunMetrics`, `PhaseStatus`, `SubStepStatus`, `ColumnProfile`, `CostBreakdown`. **No `KernelState`.** Adjust `PhaseStatus.id` to `'phase1' \| 'phase2'` with nested `steps`. | Frontend | A13, A14 | Low |
| A16 | New hooks: `useRunMetrics` (subscribes `metrics_snapshot`), `usePhases` (subscribes `phase_update`), `useColumnProfile` (REST fetch on jobId, in-memory cache), `useKeyboardShortcuts` (key → action map). | Frontend | A15 | Medium |
| A17 | Backend tests: cost aggregator unit test, previous-job query test, columns endpoint test, cost endpoint test. | Backend tests | A10–A14 | Medium |

### Phase B — Command Center vertical

| # | Task | Layer | Depends on | Est. complexity |
|---|------|-------|------------|-----------------|
| B1 | Primitives: `frontend/src/components/command-center/primitives/Sparkline.tsx`, `MiniBars.tsx`, `Donut.tsx` — pure SVG, no chart lib. Port from `shared.jsx` in the design file. | Frontend | A1, A2 | Low |
| B2 | `formatters.ts` extensions: `formatDelta(current, previous, lowerIsBetter)`, `formatCost(usd)`, `formatBytes(b)`. | Frontend | — | Low |
| B3 | `colorScales.ts` — dtype/role → token color (target/metric → turquoise, dim → violet, pii → warn). | Frontend | A1 | Low |
| B4 | `CommandCenterView.tsx` — top-level orchestrator with `MainGrid` (270 / 1fr / 320). | Frontend | A16 | Medium |
| B5 | `TopStrip.tsx` = `JobIdentity` + `KpiRow` + `ActionsCluster`. KPI delta chips render only when `previous_job_id != null`. Memoized `KpiCell` per metric. | Frontend | B2, B4 | Medium |
| B6 | `PipelineRail.tsx` + `PhaseBlock.tsx` — 2 top-level phase blocks. Within each, render the sub-steps that apply to the phase, with active sub-step pulsing. Sub-steps that don't apply to the current mode render greyed (per R12). Click an agent name → drawer with filtered events (Phase 2 stretch — ship without if needed). | Frontend | B1, A16 | Medium |
| B7 | `ColumnInspector.tsx` + `ColumnList` + `ColumnDetailCard.tsx`. Selection in client state only. Mini-bars derived from `ColumnProfile.histogram`. Role chips per spec colours (R12 colours from `colorScales`). | Frontend | B1, A16 | Medium |
| B8 | `CostBreakdown.tsx` panel — per-phase rows + total + "estimate" badge when `is_estimate`. | Frontend | A12, A16 | Low |
| B9 | `QuestionCard.tsx` — read-only display of the user question. | Frontend | B4 | Low |
| B10 | Wire `JobDetailsPage` to render `CommandCenterView` when `VITE_FEATURE_COMMAND_CENTER` is true; legacy view otherwise. One-line gate. | Frontend | A3, B4–B9 | Low |
| B11 | Component tests: `ColumnInspector` selection updates synchronously; `TopStrip` delta-chip visibility logic; `PipelineRail` greying for skipped sub-steps. | Frontend tests | B5–B7 | Medium |

### Phase C — Polish

| # | Task | Layer | Depends on | Est. complexity |
|---|------|-------|------------|-----------------|
| C1 | `PreviewTabs.tsx` shell with scroll-position preservation per tab. Default tab = Visual. | Frontend | B4 | Medium |
| C2 | `VisualPanel` (chart + time-range buttons), `DataPanel` (head() of resulting df), `LogsPanel` (port of legacy log view). | Frontend | C1 | Medium |
| C3 | `CodePanel` — streaming Python from codegen agent events. Streaming pill (●) → ready (●) on phase done. Virtualized container if >2000 lines. | Frontend | C1 | Medium |
| C4 | `EventStream.tsx` — port of legacy logs panel + filters. Virtualize via `react-window` when entries >500. | Frontend | A16 | Medium |
| C5 | `TrafficRow.tsx` — 3 sparklines: LLM/min, tok/s, validators. Pulled from `metrics_snapshot` history (rolling 60-pt window in `useRunMetrics`). | Frontend | A16, B1 | Low |
| C6 | `StatusBar.tsx` — **retries, cache hits, keyboard shortcut hints only**. (No kernel state in V1.) | Frontend | A16 | Low |
| C7 | Wire keyboard shortcuts via `useKeyboardShortcuts`: `J/K` to nav `EventStream`, `1–4` to switch tabs, `⌘↩` to re-run job, `Esc` to clear column selection. `⌘K` focuses search (full palette is V2). | Frontend | A16, C1, C4 | Low |
| C8 | A11y pass: every interactive element keyboard-reachable, focus-ring preserved, aria-labels on chips and dots. Run Lighthouse, fix to ≥95. | Frontend | C1–C7 | Medium |
| C9 | Perf pass: `React.memo` on `KpiCell`, `PhaseBlock`, `SubStepRow`, `AgentRow`. Profile a 5-minute run; assert <16ms render budget for top strip + rail under 500ms metric pushes. | Frontend | All | Medium |
| C10 | Bundle budget verification: `vite build`, diff gzipped JS vs. main; assert ≤ +30KB. | Frontend | All | Low |
| C11 | Update `frontend/.env.example` and `README` with the new flag. Update `docs/architecture.md` with the 2-phase pipeline + 22 agents. | Docs | A3 | Low |
| C12 | Deprecate `AgentTrace.tsx` — leave the file but mark the export `@deprecated`; remove it once the flag is removed in a follow-up. | Frontend | B10 | Low |

---

## 6. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| 500ms metrics push overwhelms render budget on slower laptops. | Medium | Medium | `React.memo` on hot components; profile early in Phase C; if needed, decouple `metrics_snapshot` cadence to 1s. |
| Per-phase cost rollup gets totals wrong (over- or under-counts vs. existing job-total). | Medium | Medium | Dual-emit during Phase A: keep the existing `cost_estimate` JSON unchanged; add `cost_breakdown` alongside. Add an invariant test: sum of breakdown ≈ total within 1¢. |
| Heuristic misses phrasings the LLM caught (e.g. "next month numbers" → forecasting). | Medium | Low | Chip is suggestion-only; user always confirms. Add ~10 representative prompts to the test corpus and iterate the keyword list before ship. |
| `previous_job` lookup is wrong (false positive — different data, same csv hash by coincidence; or false negative — same data, different hash because of trailing newline). | Low | Low | Use a stable hash over the parsed CSV bytes (after read), not the raw upload. Document the hashing rule. |
| Backend WS aggregator becomes a bottleneck under concurrent runs. | Low | Medium | Aggregator runs per-job, not globally — concurrent runs each emit at 500ms with no shared lock. Load-test with 4 parallel jobs. |
| Feature flag drift — code paths diverge and the legacy view rots. | Medium | Low | Set a deletion target on the legacy view (`AgentTrace`, etc.) — schedule a follow-up agent to remove the flag in 6 weeks (offer at end of plan). |
| Lighthouse a11y regression because of new SVG primitives without aria labels. | Medium | Low | Aria-label every Sparkline/MiniBar/Donut with an alt summary. Add a manual a11y task to Phase C. |
| Legacy users on browsers that don't load JetBrains Mono fall back to system mono — numbers will look slightly different from the design. | Low | Low | Specify a clean fallback stack (`'JetBrains Mono', ui-monospace, SFMono-Regular, monospace`). Acceptable. |

---

## 7. Rollback & Migration Strategy

### Data migration
- **Before**: `Job` table has no `csv_hash`. Cost stored only as a job-level `cost_estimate` JSON.
- **After**: `Job.csv_hash` (varchar, nullable) added. Optional `Job.cost_breakdown` (JSON) added.
- **Migration approach**: Additive only. New columns nullable; legacy rows untouched. No backfill required.
- **Backward compatibility**: Legacy rows with `csv_hash = NULL` simply don't surface as previous-job matches — KPI deltas just don't render. Acceptable.
- **Reversibility**: A reverse migration drops the columns. No data loss because no consumer outside this feature uses them.

### API migration
- **New endpoints** (`/jobs/{id}/columns`, `/jobs/{id}/cost`) — purely additive, no consumer impact.
- **New WS events** (`metrics_snapshot`, `phase_update`) — purely additive, old clients ignore them.
- **Mode-suggest LLM endpoint** (`AnalysisAPI.suggestMode`): no longer called by the frontend. Leave the endpoint live for one release cycle; remove in a follow-up after confirming no external callers.
- **Deprecation plan**: Document in CHANGELOG; remove the endpoint in V1.1.

### Rollback plan
- **Trigger**: Lighthouse drop, p95 render budget breach, or analyst-reported regression.
- **Step 1**: Set `VITE_FEATURE_COMMAND_CENTER=false` in env, redeploy frontend (≤2 min). Legacy `JobDetailsPage` returns.
- **Step 2** (if backend issue): Revert per-phase cost aggregation commit (the existing `cost_estimate` JSON is unchanged, so this is safe).
- **Step 3** (if data issue): Reverse the migration. Columns are nullable and unused outside this feature — safe to drop.
- **Time to rollback**: <5 min for frontend flag, <30 min for backend revert.
- **Feature flag**: Yes — `VITE_FEATURE_COMMAND_CENTER` is the master switch.

---

## 8. Post-Deployment Monitoring

### Success metrics

| Metric | Measurement method | Target | Alert threshold |
|--------|--------------------|--------|------------------|
| Time-to-interactive on `/jobs/:id` (flag on) | Browser perf timing logged on mount | ≤1s p95 | >2s p95 over 1 hour |
| Render budget on `metrics_snapshot` | React profiler in dev; production sampling via `performance.now()` around top-strip render | <16ms p95 | >32ms p95 |
| Mode-suggestion latency | Heuristic timing logged on debounced fire | <50ms p99 | >100ms p99 (would indicate something pathological) |
| Mode-suggestion no-network invariant | Synthetic test in CI that loads the app with network blocked and types a prompt | Zero network calls | Any call → CI fails |
| Per-phase cost sum vs. job total | Invariant test in test suite | abs(sum − total) ≤ $0.01 | >$0.10 drift |
| Bundle size (gzipped) | CI build step diff vs. main | ≤ +30KB | >+30KB → fail PR |
| Lighthouse a11y on `/jobs/:id` | Manual run + monthly scheduled check | ≥95 | <90 |
| Feature flag adoption | % of users with flag on | grow weekly | flat for 2 weeks → investigate |

### Monitoring period
- **Intensive (first 48h after flag turns on for first cohort)**: actively watch error logs, render-budget telemetry, and analyst feedback. WS reconnect rate is the canary.
- **Steady state (after 48h)**: automated CI checks + Lighthouse monthly.

### Signals to watch
- **Positive**: analysts spending more time in `/jobs/:id`; reduced clicks-per-session to find column stats; reduced "where is X" support questions.
- **Negative**: WS reconnect spikes, browser memory growth in long-running tabs, Lighthouse drops, "unable to find feature X" reports.
- **Leading**: render-budget telemetry creeping above 16ms — fix before users complain.

### Incident response
- **Owner during initial rollout**: the engineer who shipped the flag flip.
- **Escalation**: backend issue → backend owner; render perf → frontend owner.
- **Rollback decision criteria**: Lighthouse < 90 OR p95 render > 32ms for >1h OR ≥3 unrelated user-reported regressions → flip flag off; investigate; re-roll.

---

## 9. Open Questions

1. **DB migration tooling** — confirm whether the project uses Alembic or a different migration runner. The plan assumes Alembic; if it's something else, A8 needs adjustment.
2. **csv_hash for SQL ingestion path** — when input is SQL (`db_uri + db_query`) rather than CSV upload, what is hashed? Proposal: hash the resulting parsed CSV after `data_ingestion.ingest_from_sql()` materialises it; same hash function downstream. Confirm this is acceptable for previous-job matching across SQL re-runs.
3. **"Extensions" placement in PipelineRail** — code lives at `src/agents/extensions/` (top-level, not under `phase1/` or `phase2/`). Should the UI render Extensions as a third top-level block, or fold it under Phase 1 (since it runs before Phase 2 strategy)? Recommendation: render under Phase 1 as a sub-step labelled "Extensions" — matches the spec's flat list while honouring the 2-phase top-level decision.
4. **Drawer-on-agent-click** (PhaseBlock) — spec marks this as "Phase 2 — ship without if needed." Confirm we ship V1 without and add later, or include a minimal version.
5. **Re-run button payload** — `⌘↩` re-runs with same params. Should `use_cache` flip to `false` to force a fresh run, or honour the original `use_cache` setting?
6. **Analytics/telemetry** — do we have a usage-tracking pipeline today? Some monitoring metrics (time-to-interactive, render budget) need a sink. If absent, log to `console.info` with a stable prefix and revisit later.

---

## Appendix A — Path corrections vs. HANDOFF.md

The handoff uses `src/...` paths (e.g. `src/components/command-center/`). The actual frontend is rooted at `frontend/src/...`. Every path in this plan reflects the correct location:

| Spec path | Correct path |
|-----------|--------------|
| `src/components/command-center/` | `frontend/src/components/command-center/` |
| `src/hooks/useRunMetrics.ts` | `frontend/src/hooks/useRunMetrics.ts` |
| `src/utils/modeHeuristic.ts` | `frontend/src/utils/modeHeuristic.ts` |
| `src/api.ts` | `frontend/src/api.ts` |
| `src/index.css` | `frontend/src/index.css` |
| `src/pages/JobDetailsPage.tsx` | `frontend/src/pages/JobDetailsPage.tsx` |

Backend paths (`src/server/*`, `src/agents/*`, `src/workflow/*`) are correct as-is — backend is the top-level `src/`.

---

## Appendix B — Decisions log (from planning)

| # | Question | Decision |
|---|----------|----------|
| 1 | Phase model — 5 flat phases (spec) or 2 actual top-level phases? | **2 actual top-level phases**. The 5 sub-step labels (Profiling/Extensions/Strategy/Codegen/Validate) are surfaced *within* each phase. 22 real agents (not 27) drive `agents_total` dynamically. |
| 2 | KernelState in StatusBar? | **Out of scope for V1.** StatusBar shows retries, cache hits, and keyboard shortcut hints only. No `useKernelState` hook, no kernel endpoint. |
| 3 | Per-phase cost breakdown — add to token tracker, or expose flat total? | **Add per-phase aggregation** to the token tracker. `/jobs/{id}/cost` returns per-phase rows. |
| 4 | Previous-job lookup for KPI deltas? | **Implement** `(user_id, mode, csv_hash)` lookup. Adds a `csv_hash` column to `Job`. |
| 5 | Feature flag? | **`VITE_FEATURE_COMMAND_CENTER` env var** with a one-line gate in `JobDetailsPage`. |
| 6 | Exploratory mode in PipelineRail? | **Show all 5 sub-steps**, greying out the inactive ones. Analysts learn the full pipeline shape. |
| 7 | Living spec vs. one-off plan? | **One-off plan** at `docs/plans/ui-refresh-plan.md` (this file). |
