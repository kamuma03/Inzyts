# System Architecture Documentation

**Status**: Beta

## 1. System Overview

**Inzyts - Analyze. Predict. Discover.** is an automated pipeline designed to take raw data (CSV, SQL databases, cloud storage, or REST APIs) and user intent as input, and produce high-quality, executable Jupyter Notebooks as output.

It employs a **Seven-Mode Pipeline** with **27 Specialized Agents** orchestrated by **LangGraph**:

*   **Exploratory Mode**: Data profiling, quality assessment, and LLM-powered insights. Ideal for initial data discovery.
*   **Predictive Mode**: ML model training with classification/regression algorithms.
*   **Diagnostic Mode**: Root cause analysis with causal inference and feature importance.
*   **Comparative Mode**: A/B testing and cohort comparison with statistical tests.
*   **Forecasting Mode**: Time series analysis with ARIMA, Prophet, and seasonal decomposition.
*   **Segmentation Mode**: Customer/data clustering with K-means, DBSCAN, and persona creation.
*   **Dimensionality Mode**: Feature reduction using PCA/t-SNE with automatic assessment.

### Key Features

#### Multi-Mode Analysis Pipeline
*   **27-Agent Architecture**: Specialized agents for each pipeline mode with dedicated strategy, code generation, and validation.
*   **7-Mode Execution**: Supports exploratory, predictive, diagnostic, comparative, forecasting, segmentation, and dimensionality workflows.
*   **Extension System**: Mode-specific preprocessing agents (Forecasting, Comparative, Diagnostic Extensions).

#### Dimensionality Reduction
*   **Dedicated Pipeline Mode**: PCA analysis with Scree plots, 2D/3D projections, and component loadings.
*   **PCA Assessment**: Automatic evaluation of when dimensionality reduction is applicable based on feature count.
*   **t-SNE Support**: Non-linear dimensionality reduction for complex data visualization.

#### Data Quality & Remediation
*   **Automated Detection**: Identifies missing values, duplicates, outliers, type mismatches, and other quality issues.
*   **Safety-Rated Remediation**: 25+ remediation strategies with safety ratings (SAFE, REVIEW, RISKY, DANGEROUS).
*   **Dual-Path Analysis**: Generate notebooks comparing original vs. remediated data side-by-side.

#### Data Ingestion & Management
*   **SQL Database Integration**: Connect to any SQL database. Extract data autonomously via an LLM agent translating natural language to SQL, or explicitly via bridged SQL queries.
*   **Cloud Data Warehouses**: Native support for BigQuery, Snowflake, Redshift, and Databricks via SQLAlchemy dialects with warehouse-specific URI schemes.
*   **Cloud Storage Ingestion**: Pull data from AWS S3, Google Cloud Storage, and Azure Blob Storage. Supports CSV, JSON, Excel, and Parquet with automatic format conversion. File size limits enforced; credentials sourced from environment variables only.
*   **REST API Data Extraction**: Fetch data from REST APIs with Bearer token, API key, or Basic auth. JMESPath-based response extraction, configurable timeouts, and SSRF protection (blocks private/reserved IP ranges).
*   **Multi-File CSV Support**: Load and analyze multiple CSV files with intelligent join detection and relationship mapping.
*   **Domain Template System**: Upload and manage domain-specific templates for consistent analysis patterns across projects.
*   **Data Dictionary Integration**: Parse and apply data dictionaries for enhanced column understanding and business context.
*   **Exclude Columns**: Explicitly filter out sensitive or irrelevant columns from analysis to improve focus and privacy.

#### ML & Hyperparameter Tuning
*   **Parameter Tuning Codegen**: Generate hyperparameter tuning code with GridSearchCV and custom parameter grids.
*   **Auto Model Selection**: Intelligent algorithm selection based on target column and data characteristics.

#### Live Notebook Execution
*   **Browser-Based Execution**: Execute generated notebooks directly in the browser with live Jupyter kernel integration.
*   **JupyterService Proxy**: Seamless communication with Jupyter Server for kernel management and cell execution.
*   **Real-time Output**: WebSocket-based streaming of cell outputs, plots, and errors.

#### Interactive Notebooks (Cell-Level Editing)
*   **CellEditAgent**: Lightweight micro-agent for modifying individual notebook cells via natural language instructions.
*   **KernelSessionManager**: Persistent Jupyter kernel sessions with 30-minute idle TTL and automatic cleanup.
*   **Inline Chart Rendering**: Base64-encoded matplotlib/seaborn charts rendered directly in the interactive cell viewer.
*   **Three View Modes**: Static HTML, Interactive (cell-level editing), and Live JupyterLab.

#### Conversational Follow-Up Analysis
*   **FollowUpAgent**: Generates new notebook cells (code + markdown) from follow-up questions, leveraging existing kernel state.
*   **Question Classification**: Automatically categorizes questions as drill-down, what-if, comparison, or explain.
*   **Persistent Conversations**: Q&A history stored in PostgreSQL (`conversation_messages` table), surviving server restarts.
*   **Kernel Introspection**: Dynamic capture of live kernel variables, DataFrame shapes, and model objects for richer context.

#### Report Export & Intelligence
*   **Multi-Format Export**: Generate reports in PDF (WeasyPrint), HTML (Jinja2), PowerPoint (python-pptx), and Markdown from completed analyses.
*   **Executive Summary Generator**: LLM-powered service that produces structured key findings, data quality highlights, and actionable recommendations with automatic fallback to notebook text extraction.
*   **PII Detection & Masking**: Regex-based scanner for emails, phone numbers, SSNs, credit cards, and IP addresses in notebook content. Optional masking replaces detected PII with redacted placeholders before export.
*   **Branded Reports**: Styled HTML template with Inzyts branding, metadata header, executive summary section, PII warning banner, and execution metrics table.

#### Core System Capabilities
*   **Auto-Caching**: Validation profiles cached (`~/.Inzyts_cache`) for instant mode switching without re-running profiling.
*   **Profile Lock**: Immutable snapshot of data understanding that prevents "concept drift" between phases.
*   **Self-Correction**: Recursive validation loops to improve code/logic within each phase.
*   **Modern UI**: Real-time agent trace, token tracking, and Ink Black theme with gradient accents.

### System Flow Architecture (Seven-Mode Pipeline)

```
CSV Input + User Intent + Question + Mode
    ↓
[Orchestrator] ═══════════════════════════════════════════════════════════════╗
    │  (27-Agent Coordination)                                                 ║
    ├── 1. Check explicit --mode flag (exploratory/predictive/diagnostic/    ║
    │                    comparative/forecasting/segmentation/dimensionality) ║
    ├── 2. Check --target presence (implies predictive)                       ║
    ├── 3. Keyword inference from question (7-mode detection)                 ║
    ├── 4. Default: EXPLORATORY                                               ║
    │                                                                          ║
    ├── Check cache: ~/.Inzyts_cache/{csv_hash}/                            ║
    │   ├── NOT_FOUND → Run Phase 1                                           ║
    │   ├── VALID → Restore cached profile, skip to Extensions/Phase 2        ║
    │   ├── EXPIRED → Delete cache, run Phase 1                               ║
    │   └── CSV_CHANGED → Warn user, offer options                            ║
    │                                                                          ║
    ↓                                                                          ║
╔════════════════════════════════════════════════════════════════════════════╗ ║
║ PHASE 1: Data Understanding (3 Agents)                                     ║ ║
║                                                                             ║ ║
║   [Data Profiler] ──→ [Profile Code Generator] ───┐                        ║ ║
║         ↑                                         ↓                        ║ ║
║         └─────────── [Profile Validator] ─────────┘                        ║ ║
║                            │                                               ║ ║
║                   ┌────────────────┐                                       ║ ║
║                   │ PROFILE LOCK   │                                       ║ ║
║                   │  + Save Cache  │ → ~/.Inzyts_cache/{csv_hash}/       ║ ║
║                   └────────────────┘                                       ║ ║
╚══════════════════════════╪═════════════════════════════════════════════════╝ ║
                           │                                                    ║
                           ↓                                                    ║
╔════════════════════════════════════════════════════════════════════════════╗ ║
║ EXTENSIONS: Mode-Specific Preprocessing (3 Agents)                         ║ ║
║                                                                             ║ ║
║  [Forecasting Extension] → Time parsing, seasonality detection             ║ ║
║  [Comparative Extension] → Group identification, cohort analysis           ║ ║
║  [Diagnostic Extension]  → Correlation analysis, causal relationships      ║ ║
║                                                                             ║ ║
║  Note: Only runs if mode requires (forecasting, comparative, diagnostic)   ║ ║
╚══════════════════════════╪═════════════════════════════════════════════════╝ ║
                           │                                                    ║
            ┌──────────────┴───────────────────────────┐                       ║
            ↓      ↓        ↓        ↓        ↓      ↓      ↓                  ║
  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐║
  │EXPLORAT│ │PREDICTIV│ │DIAGNOST│ │COMPARAT│ │FORECAST│ │SEGMENT.│ │DIMENSIO│║
  └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘║
       │          │          │          │          │          │          │     ║
       ↓          ↓          ↓          ↓          ↓          ↓          ↓     ║
╔══════════╗ ╔══════════╗ ╔══════════╗ ╔══════════╗ ╔══════════╗ ╔══════════╗ ╔══════════╗
║ Conclus. ║ ║ Strategy ║ ║ Root     ║ ║ A/B Test ║ ║ TimeSeries║ ║ Cluster  ║ ║ PCA      ║
║ Agent    ║ ║ Agent    ║ ║ Cause    ║ ║ Agent    ║ ║ Agent    ║ ║ Agent    ║ ║ Agent    ║
║ (1)      ║ ║    ↓     ║ ║ Agent    ║ ║    ↓     ║ ║    ↓     ║ ║    ↓     ║ ║    ↓     ║
║          ║ ║ CodeGen  ║ ║    ↓     ║ ║ CodeGen  ║ ║ CodeGen  ║ ║ CodeGen  ║ ║ CodeGen  ║
║          ║ ║    ↓     ║ ║ CodeGen  ║ ║    ↓     ║ ║    ↓     ║ ║    ↓     ║ ║    ↓     ║
║          ║ ║Validator ║ ║    ↓     ║ ║Validator ║ ║Validator ║ ║Validator ║ ║Validator ║
║          ║ ║          ║ ║Validator ║ ║          ║ ║          ║ ║          ║ ║          ║
╚══════════╝ ╚══════════╝ ╚══════════╝ ╚══════════╝ ╚══════════╝ ╚══════════╝ ╚══════════╝
       │          │          │          │          │          │          │     ║
       └──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘     ║
                                  │                                             ║
                                  ↓                                             ║
[Orchestrator] ←══════════════════════════════════════════════════════════════╝
    ↓
    │  EXPLORATORY:    Profile + Conclusions
    │  PREDICTIVE:     Profile + ML Models
    │  DIAGNOSTIC:     Profile + Extension + Root Cause Analysis
    │  COMPARATIVE:    Profile + Extension + A/B Testing
    │  FORECASTING:    Profile + Extension + Time Series Forecast
    │  SEGMENTATION:   Profile + Customer Segments
    │  DIMENSIONALITY: Profile + PCA/t-SNE Analysis
    ↓
Output: Jupyter Notebook (.ipynb)
```

## 2. Architecture Decisions & Rationale (ADR)

### ADR 1: Dual-Phase Architecture (Split Understanding vs. Analysis)
*   **Decision**: Strictly separate data profiling (Phase 1) from analysis planning (Phase 2).
*   **Rationale**: Large Language Models (LLMs) act as excellent "code writers" but unreliable "data readers." If an LLM tries to plan an ML model *before* it knows if a column is numeric or categorical, it hallucinates. By forcing a dedicated "Data Understanding" phase that must be validated *before* any analysis is planned, we eliminate schema hallucinations. Phase 2 operates on a trusted, locked profile, not raw assumptions.

### ADR 2: Profile Lock Mechanism
*   **Decision**: Implement an immutable `ProfileToStrategyHandoff` object that cannot be modified after Phase 1.
*   **Rationale**: Prevents "Concept Drift" during analysis. If the Strategy Agent decides "Column A is a Date" after the Profiler proved it was "String," the code will crash. The Profile Lock acts as a contract: Phase 2 MUST accept the Phase 1 findings as ground truth.

### ADR 3: LangGraph for Orchestration
*   **Decision**: Use `LangGraph` (stateful graph) instead of linear chains or simple DAGs.
*   **Rationale**: The system requires **recursion** (loops). If validaton fails, we need to route *backwards* (e.g., `Validator -> CodeGen`). Linear chains (like standard LangChain) handle this poorly. LangGraph manages the global state (`AnalysisState`) and allows for conditional edges based on validation results, enabling the self-correcting behavior.

### ADR 4: Pydantic for Inter-Agent Handoffs
*   **Decision**: Enforce strict Pydantic schemas for all agent outputs (`src/models/handoffs.py`).
*   **Rationale**: LLM outputs are unstructured text. To chain agents, Agent A's output must be Agent B's exact input. Pydantic forces the LLM (via function calling or JSON mode) to structure its thinking. If the output doesn't match the schema (e.g., missing fields), it fails fast before propagating garbage downstream.

### ADR 5: Sandbox Execution for Validation
*   **Decision**: Validators must execute generated code in a sandbox (`src/core/sandbox.py`) rather than just reading it.
*   **Rationale**: Code can look syntactically correct but fail at runtime (e.g., `KeyError: 'column_name'`, empty plot). Static analysis is insufficient for data science code. The Validators run the actual code on the actual data to verify that assets (plots, variables) are created.

### ADR 6: Profile Caching & Upgradability
*   **Decision**: Store successful Phase 1 profiles in `~/.Inzyts_cache` keyed by CSV hash.
*   **Rationale**: Phase 1 (Profiling) is computationally expensive and deterministic for a given dataset version. By caching the validated profile, we enable a "Chat with Data" experience (Exploratory Mode) that can be instantly upgraded to "Train a Model" (Predictive Mode) without forcing the user to wait for profiling again.

### ADR 7: Mode Inference
*   **Decision**: Use keyword matching across 7 modes to infer user intent if not explicitly flagged.
*   **Rationale**: Users often don't know the terminology. Different questions imply different modes:
    - "What is the distribution?" → Exploratory
    - "Predict churn" → Predictive
    - "Why did sales drop?" → Diagnostic
    - "Compare A vs B" → Comparative
    - "Forecast next quarter" → Forecasting
    - "Segment customers" → Segmentation
    - "Reduce dimensions" / "PCA analysis" → Dimensionality
*   Automatically routing to the correct pipeline reduces friction and ensures optimal analysis approach.

### ADR 8: Extension System
*   **Decision**: Introduce mode-specific preprocessing agents that run between Phase 1 and Phase 2.
*   **Rationale**: Certain modes require specialized data preparation:
    - **Forecasting**: Needs date parsing, seasonality detection, temporal feature engineering
    - **Comparative**: Requires group identification, cohort analysis, baseline detection
    - **Diagnostic**: Needs correlation analysis, causal relationship mapping
*   Extensions enrich the locked profile with mode-specific context without re-profiling.
*   Extensions only run when needed, keeping other modes lightweight.

### ADR 9: 27-Agent Specialization
*   **Decision**: Expand to 27 agents with mode-specific strategy, codegen, and validation agents.
*   **Rationale**:
    - Each mode has unique requirements (time series vs clustering vs A/B testing vs dimensionality reduction)
    - Generic "one-size-fits-all" agents lead to poor code quality and hallucinations
    - Specialized agents with mode-specific prompts produce better, more accurate analysis
    - Validation criteria differ by mode (RMSE for forecasting, p-values for comparative, silhouette for clustering, variance explained for PCA)
*   Trade-off: Increased complexity for significantly better analysis quality per mode.

## 3. Directory Structure & File Manifest

### 3.1 Root Source (`src/`)

#### `src/main.py`
*   **What it is**: The CLI entry point.
*   **Key Responsibilities**:
    *   Parses new args (`--mode`, `--use-cache`, `--target`).
    *   Initializes `AnalysisState` with cache/mode logic.
    *   Compiles and runs the `LangGraph` app.
    *   Handles interactive cache prompts.

#### `src/config.py`
*   **What it is**: Single Source of Truth for configuration.
*   **Key Responsibilities**:
    *   Phase thresholds, timeouts, and agent-specific params.
    *   Links to LLM variants (Ollama/Anthropic).

### 3.2 Models (`src/models/`)

#### `src/models/state.py`
*   **What it is**: Global execution state.
*   **Key Fields**: `pipeline_mode`, `cache_status`, `using_cached_profile`, `remediation_plans`, `dimensionality_outputs`.

#### `src/models/handoffs.py`
*   **What it is**: Data Contracts.
*   **Key Models**: `ExploratoryConclusionsOutput`, `PipelineMode` Enum, `RemediationPlan`, `QualityIssue`, `PCAConfig`.

### 3.3 Agents (`src/agents/`)

#### `src/agents/sql_agent.py`
*   **What it is**: Autonomous SQL extraction agent — introspects database schema, generates a read-only `SELECT` query from natural language, validates it, and saves results as a CSV for downstream analysis.
*   **Key Responsibilities**:
    *   Connects to the target database via `SQLDatabase.from_uri()` and extracts the schema.
    *   Invokes the LLM with the schema + user question to generate a SQL query.
    *   Validates the query with `sqlglot` AST parsing — only plain `SELECT` statements are allowed; any DML (including CTE-embedded DML) is rejected.
    *   Enforces a row cap (`SQL_MAX_ROWS`, default 200,000) and a **column cap** (`SQL_MAX_COLS`, default 500) to prevent memory exhaustion.
    *   Rejected queries are logged at `WARNING` level with a 200-char query preview for security audit.
    *   Supports cloud data warehouses (BigQuery, Snowflake, Redshift, Databricks) via SQLAlchemy dialect URIs.

#### `src/agents/api_agent.py`
*   **What it is**: REST API data extraction agent — fetches data from external APIs, handles authentication and pagination, extracts tabular data, and saves results as CSV.
*   **Key Responsibilities**:
    *   Validates the target URL against private/reserved IP ranges (SSRF protection); `localhost`/`127.0.0.1` allowed for development.
    *   Builds authentication headers from configuration: Bearer token, API key (custom header name), or Basic auth.
    *   Fetches data with configurable timeout (`API_TIMEOUT`, default 30s) and response size limit (`API_MAX_RESPONSE_SIZE`, default 100 MB).
    *   Extracts tabular data from JSON responses using JMESPath expressions or auto-detection of common keys (`data`, `results`, `items`, `records`).
    *   Normalizes nested JSON into a flat DataFrame via `pd.json_normalize()` and saves as CSV.

#### `src/agents/orchestrator.py`
*   **What it is**: The Project Manager (Coordinates 27 agents across 7 modes).
*   **Key Responsibilities**:
    *   **Mode Detection**: Determines which of 7 modes to use based on input.
    *   **Cache Management**: Checks for collisions/expiry, triggers save/restore.
    *   **Agent Routing**: Coordinates all 27 agents across phases and extensions.
    *   **Token Tracking**: Aggregates token usage across all agent invocations.

#### `src/server/services/progress_tracker.py`
*   **What it is**: Redis-backed progress tracking service with timing, ETA, and database persistence.
*   **Key Responsibilities**:
    *   **Event-to-Progress Mapping**: Maps structured log events (e.g., `PHASE1_START`, `VALIDATION_PASSED`) to progress percentages via `EVENT_PROGRESS_MAP`.
    *   **Timing & ETA**: Tracks `started_at`, per-phase start/latest timestamps, and calculates linear ETA extrapolation.
    *   **Backward Prevention**: Progress only advances forward — later events with lower percentages are ignored.
    *   **DB Persistence**: Writes `JobProgress` rows to PostgreSQL on every progress advance for API-accessible history.
    *   **Redis Storage**: Uses Redis hashes for low-latency reads by the Socket.IO handler during real-time streaming.

#### `src/server/services/engine.py` — SocketIOHandler
*   **What it is**: Custom `logging.Handler` that bridges structured log events to Socket.IO clients.
*   **Key Responsibilities**:
    *   **Event Detection**: Checks `hasattr(record, "event")` to identify structured events from `log_event()`.
    *   **Agent Event Emission**: Emits `agent_event` Socket.IO events with event name, phase, and agent info.
    *   **Progress Emission**: Calls `ProgressTracker.update_from_event()` then emits `progress` events with percentage, message, ETA, elapsed time, and phase timings.
    *   **Graceful Degradation**: ProgressTracker failures (Redis down) don't break job execution.

#### `src/agents/base.py`
*   **What it is**: Base class wrapping `CrewAI` with LLM provider abstraction.

#### Phase 1: Data Understanding (3 Agents - Common to All Modes)
*   **`phase1/data_profiler.py`**: The Analyst. Hybrid LLM + heuristic type detection, quality issue detection.
*   **`phase1/profile_codegen.py`**: The Developer. Generates profiling cells with templates + remediation code.
*   **`phase1/profile_validator.py`**: The QA. Sandbox execution, PEP8 validation, grants profile lock.

#### Extensions: Mode-Specific Preprocessing (3 Agents)
*   **`extensions/forecasting_extension_agent.py`**: Time series specialist. Parses dates, detects seasonality.
*   **`extensions/comparative_extension_agent.py`**: Group analysis specialist. Identifies A/B groups, cohorts.
*   **`extensions/diagnostic_extension_agent.py`**: Causal analysis specialist. Maps correlations, dependencies.

#### Exploratory Mode (1 Agent)
*   **`phase1/exploratory_conclusions.py`**: The Synthesizer. LLM-powered insights without modeling.

#### Predictive Mode (3 Agents)
*   **`phase2/strategy.py`**: The Data Scientist. Plans ML modeling approach.
*   **`phase2/analysis_codegen.py`**: The ML Engineer. Generates Scikit-Learn code.
*   **`phase2/analysis_validator.py`**: The Tech Lead. Validates model training and metrics.

#### Diagnostic Mode (3 Agents)
*   **`phase2/diagnostic_strategy.py`**: Root cause strategist. Plans causal analysis.
*   **`phase2/analysis_codegen.py`**: Generates diagnostic code (SHAP, feature importance).
*   **`phase2/analysis_validator.py`**: Validates diagnostic metrics.

#### Comparative Mode (3 Agents)
*   **`phase2/comparative_strategy.py`**: Statistical testing strategist. Plans A/B tests.
*   **`phase2/analysis_codegen.py`**: Generates comparison code (t-tests, chi-square).
*   **`phase2/analysis_validator.py`**: Validates statistical significance.

#### Forecasting Mode (3 Agents)
*   **`phase2/forecasting_strategy.py`**: Time series strategist. Plans ARIMA/Prophet.
*   **`phase2/analysis_codegen.py`**: Generates forecasting code.
*   **`phase2/analysis_validator.py`**: Validates forecast accuracy (RMSE, MAE).

#### Segmentation Mode (3 Agents)
*   **`phase2/segmentation_strategy.py`**: Clustering strategist. Plans K-means/DBSCAN.
*   **`phase2/analysis_codegen.py`**: Generates clustering code.
*   **`phase2/analysis_validator.py`**: Validates cluster quality (silhouette score).

#### Dimensionality Mode (3 Agents)
*   **`phase2/dimensionality_strategy.py`**: Feature reduction strategist. Plans PCA/t-SNE analysis.
*   **`phase2/analysis_codegen.py`**: Generates dimensionality reduction code.
*   **`phase2/analysis_validator.py`**: Validates variance explained, component quality.

### 3.4 Workflow (`src/workflow/`)

#### `src/workflow/graph.py`
*   **What it is**: The wiring.
*   **Key Responsibilities**:
    *   Defines the conditional branching (`route_after_user_intent`, `route_after_profile_validation`).
    *   Manages the "Upgrade Path" (skipping Phase 1 if using cache).

### 3.5 Utils (`src/utils/`)

#### `src/utils/file_utils.py`
*   **What it is**: Robust File Loading Utilities.
*   **Key Responsibilities**:
    *   `detect_csv_dialect()`: Auto-detect CSV delimiters and quote characters using `csv.Sniffer`.
    *   `load_csv_robust()`: Load CSV/log files with automatic delimiter detection, multi-encoding fallback (`utf-8`, `utf-8-sig`, `latin-1`, `cp1252`), and Python engine fallback for edge cases.
    *   Used by `DataLoader`, `DataManager`, and the file preview endpoint for unified, robust file handling across the system.

#### `src/utils/cache_manager.py`
*   **What it is**: The Cache Engine.
*   **Key Responsibilities**:
    *   Hashing CSVs (SHA256).
    *   Serializing/Deserializing Pydantic models to JSON.
    *   Managing TTL (7 days).
    *   Checking for CSV modifications.

#### Cache Directory Structure

```
~/.Inzyts_cache/
├── {csv_hash_1}/
│   ├── metadata.json          # Cache metadata
│   ├── profile_lock.json      # Locked Phase 1 outputs
│   ├── profile_cells.json     # Notebook cells from Phase 1
│   └── profile_handoff.json   # ProfileToStrategyHandoff
├── {csv_hash_2}/
│   └── ...
└── cache_index.json           # Quick lookup: csv_path → hash
```

### Detailed Component Architecture

**User Interface Layer**
- CLI Interface (main.py)
- Web Interface (FastAPI Server + React Frontend)
    ↓
**Orchestration Layer**
- Orchestrator Agent (Mode Detection, Cache Management)
- LangGraph (Workflow Engine)
    ↓
**Phase 1: Data Understanding**
- Data Profiler (Hybrid LLM + Heuristics)
    ↓
- Profile CodeGen (Jupyter Cell Generator)
    ↓
- Profile Validator (PEP8, Encoding, Performance)
    ↓ (quality >= 0.70)
- [PROFILE LOCK GRANTED] → Saved to Cache
    ↓
**Pipeline Branch**:
- If EXPLORATORY Mode:
    → Exploratory Conclusions Agent (LLM Insight Synthesis)
    → Assembly
- If PREDICTIVE Mode:
    → Strategy Agent (ML Methodology Selector)
    → Analysis CodeGen (Scikit-Learn Generator)
    → Analysis Validator (Model Quality Checker)
    → Assembly
    ↓
**Output Layer**
- Notebook Assembly (Cell Merger)
- Jupyter Notebook (.ipynb Output)

### Workflow: Exploratory Mode

**Step 1: Initialization**
```
User runs: --question "What are the patterns?"
    ↓
Orchestrator detects keywords → EXPLORATORY mode
    ↓
Cache Manager checks: NOT_FOUND
```

**Step 2: Phase 1 - Data Profiling**
```
Data Profiler analyzes CSV structure
    ↓ (ProfilerToCodeGenHandoff)
Profile CodeGen generates profiling cells
    ↓ (ProfileCodeToValidatorHandoff)
Profile Validator checks code quality
    ├─ If quality < 0.70: RETRY with feedback
    └─ If quality >= 0.70: GRANT PROFILE LOCK
        ↓
Cache Manager saves profile (7-day TTL)
```

**Step 3: Exploratory Conclusions**
```
Exploratory Conclusions Agent synthesizes insights
    ↓ (ExploratoryConclusionsOutput)
Assembly merges profile cells + conclusion cells
    ↓
Jupyter Notebook: outputs/analysis_{timestamp}.ipynb
```

### Workflow: Predictive Mode

**Step 1: Initialization**
```
User runs: --target Churn --mode predictive
    ↓
Orchestrator sets PREDICTIVE mode
    ↓
Cache Manager checks: VALID (< 7 days)
    ├─ User accepts cache: Restore ProfileToStrategyHandoff (skip Phase 1)
    └─ User rejects cache: Run Phase 1 (same as Exploratory)
```

**Step 2: Phase 2 - ML Modeling**
```
Strategy Agent plans ML strategy from locked profile
    ├─ Analyze target column type
    └─ Select models (classification/regression)
    ↓ (StrategyToCodeGenHandoff)
Analysis CodeGen generates ML code
    ├─ Create train/test split
    ├─ Generate model training cells
    └─ Generate evaluation metrics
    ↓ (AnalysisCodeToValidatorHandoff)
Analysis Validator validates ML code
    ├─ If quality < 0.70: RETRY with feedback
    └─ If quality >= 0.70: PASS
```

**Step 3: Assembly**
```
Assembly merges profile cells + ML cells
    ↓
Jupyter Notebook: outputs/analysis_{timestamp}.ipynb
```

### Workflow: Cache Upgrade (Exploratory → Predictive)

**Scenario**: User previously ran exploratory analysis, now wants predictive model

**Step 1: Cache Validation**
```
User runs: --target Churn --use-cache
    ↓
Orchestrator initializes PREDICTIVE with force_cache
    ↓
Cache Manager checks: VALID (mode=exploratory, age=2 days)
    ↓
Verify CSV hash matches cached version
    ├─ Hash matches: Proceed
    └─ Hash mismatch: ERROR - CSV file changed
```

**Step 2: Fast-Track to Phase 2**
```
Cache Manager restores ProfileToStrategyHandoff
    ↓
[SKIP PHASE 1 ENTIRELY]
    ↓
Phase 2 Pipeline:
    Strategy Agent → Analysis CodeGen → Analysis Validator
    ↓
ML cells generated
```

**Step 3: Assembly**
```
Assembly reuses cached profile cells + new ML cells
    ↓
Jupyter Notebook: outputs/analysis_{timestamp}.ipynb
✓ Predictive notebook ready in seconds
```

## 4. Data Flow

### 4.1 High-Level Data Flow

1.  **Orchestrator** Initialization:
    *   Check Cache -> Found? -> Prompt "Use Cache?".
    *   Infer Mode -> "Exploratory" (Question) or "Predictive" (Target).
2.  **Route**:
    *   **Path A (Use Cache)**: Restore `ProfileLock` -> Jump to Phase 2 (if Predictive) or Assembly (if Exploratory).
    *   **Path B (Fresh Run)**: Start Phase 1.
3.  **Phase 1** (Profiler -> CodeGen -> ValidatorLoop):
    *   Produces `ProfileLock`.
    *   **Orchestrator**: Saves `ProfileLock` to `~/.Inzyts_cache`.
4.  **Route Mode**:
    *   **Exploratory**: `ExploratoryConclusionsAgent` -> Assembly.
    *   **Predictive**: Phase 2 (Strategy -> CodeGen -> ValidatorLoop) -> Assembly.
5.  **Assembly**:
    *   Combines Cells (Profile + [Conclusions|Analysis]) -> Writes `.ipynb`.

## 5. Notebook Output Structures

### 5.1 Exploratory Mode Notebook
Focused on data understanding and answering the user's questions. Uses consistent numbered headings.

```
┌─────────────────────────────────────────┐
│ # 1. Title & Introduction               │
│    - Question: "{user_question}"        │
├─────────────────────────────────────────┤
│ ## 2. Setup & Data Loading              │
│    2.1 Imports                          │
│    2.2 Data Loading                     │  ← Phase 1 Cells
├─────────────────────────────────────────┤
│ ## 3. Data Profiling & Quality          │
│    3.1 Data Overview                    │
│    3.2 Data Quality Report              │
│    3.3 Column Analysis                  │
├─────────────────────────────────────────┤
│ ## 4. Exploratory Analysis Conclusions  │  ← Exploratory Conclusions
│    - Direct Answer                      │
│    - Key Findings                       │
│    - Statistical Insights               │
│    - Recommendations                    │
└─────────────────────────────────────────┘
```

### 5.2 Predictive Mode Notebook
Focused on building and validating machine learning models. Uses consistent numbered headings with subsections.

```
┌─────────────────────────────────────────┐
│ # 1. Title & Introduction               │
├─────────────────────────────────────────┤
│ ## 2. Setup & Data Loading              │
│    2.1 Imports                          │
│    2.2 Data Loading                     │  ← Phase 1 Cells
├─────────────────────────────────────────┤
│ ## 3. Data Profiling & Quality          │
│    3.1 Data Overview                    │
│    3.2 Data Quality Report              │
├─────────────────────────────────────────┤
│ ## 4. Analysis                          │  ← Phase 2 Cells
│    4.1 Data Preprocessing               │
│    4.2 Model Training                   │
│    4.3 Model Evaluation                 │
│    4.4 Results Visualization            │
│    4.5 Analysis Conclusions             │
└─────────────────────────────────────────┘
```

## 6. Web Interface Architecture

The Web UI providing a user-friendly layer over the CLI/API.

**Web Workflow**:
```
User uploads CSV via Browser (POST /api/v2/files/upload)
    ↓
POST /api/v2/cache/check
    ↓
Cache Manager: check_cache(hash)
    ├─ Status: NOT_FOUND → Prompt for mode selection
    ├─ Status: VALID → Show cache option (use or ignore)
    ├─ Status: EXPIRED → Auto-delete and prompt fresh analysis
    └─ Status: CSV_CHANGED → Warn user, offer options
    ↓
User clicks "Start Analysis"
    ↓
POST /api/v2/analyze (background Celery job)
    ↓
Orchestrator runs LangGraph workflow
    ├─ Real-time status updates via Socket.IO WebSocket events
    ├─ Structured agent events (agent_event + progress) with phase-aware tracking
    └─ Progress tracking: pending → running → completed (with ETA via ProgressTracker)
    ↓
GET /api/v2/jobs/{job_id} (client polls / receives WS events)
    ↓
Workflow complete
    ↓
GET /api/v2/notebooks/{job_id} → Download .ipynb
    OR
GET /api/v2/notebooks/{job_id}/html → View rendered HTML
    OR
POST /api/v2/notebooks/{job_id}/session → Start live Jupyter execution
```

**Key API Endpoints (v2)**:
- `POST /api/v2/cache/check` - Validate cache status before analysis
- `POST /api/v2/analyze` - Start background analysis job
- `GET /api/v2/jobs/{job_id}` - Get job status, progress, and logs
- `POST /api/v2/jobs/{job_id}/cancel` - Cancel running job
- `GET /api/v2/notebooks/{job_id}` - Download completed notebook
- `GET /api/v2/notebooks/{job_id}/html` - Get rendered HTML notebook
- `POST /api/v2/notebooks/{job_id}/session` - Start live Jupyter session
- `POST /api/v2/files/upload` - Upload CSV file (multipart)
- `GET /api/v2/files/preview` - Preview file content (first 5 rows) with robust delimiter detection
- `GET /api/v2/templates` - List domain templates
- `DELETE /api/v2/cache/{csv_hash}` - Clear specific cache
- `DELETE /api/v2/cache/all` - Clear all caches
- `GET /api/v2/metrics` - System health metrics
- `GET /api/v2/notebooks/{job_id}/cells` - Get notebook as structured JSON cells (for interactive mode)
- `POST /api/v2/notebooks/{job_id}/cells/edit` - Edit cell with natural language instruction (CellEditAgent + kernel execution)
- `POST /api/v2/notebooks/{job_id}/ask` - Ask follow-up question (FollowUpAgent + kernel execution + DB persistence)
- `GET /api/v2/notebooks/{job_id}/conversation` - Load full conversation history for a job
- `POST /api/v2/suggest-mode` - AI-powered analysis mode suggestion based on question keywords and target column (30 req/min)

### 6.1 Interactive Notebook Architecture

After notebook generation, users can switch to **Interactive Mode** to edit cells using natural language.

**Interactive Editing Flow**:
```
User hovers over code cell → "✨ Tweak this cell" input appears
    ↓
User types: "Make this a stacked bar chart with a vibrant palette"
    ↓
POST /api/v2/notebooks/{job_id}/cells/edit
    Body: { cell_index, current_code, instruction }
    ↓
KernelSessionManager → get_or_create_session(job_id)
    ├─ If no session: Start kernel, load dataset, capture df.dtypes
    └─ If session exists: Reuse (update last_activity timestamp)
    ↓
CellEditAgent.edit_cell(instruction, current_code, df_context)
    ├─ Builds focused prompt (~500 tokens)
    ├─ LLM generates modified Python code
    └─ Extracts code from response (strips ```python fences)
    ↓
KernelSession.execute(new_code)
    ├─ Captures stdout, stderr, display_data
    └─ Extracts base64 image/png from display_data messages
    ↓
Response: { new_code, output, images: [base64...], success }
    ↓
Frontend hot-swaps cell code + renders inline charts
```

**Key Components**:

| Component | Location | Purpose |
|-----------|----------|---------|
| `CellEditAgent` | `src/agents/cell_edit_agent.py` | Lightweight LLM agent for cell-level code modification |
| `KernelSessionManager` | `src/services/kernel_session_manager.py` | Singleton managing persistent kernel sessions per job |
| `InteractiveCell` | `frontend/src/components/InteractiveCell.tsx` | React component with per-cell chat input and chart rendering |
| `CELL_EDIT_PROMPT` | `src/prompts.py` | System prompt for the code editor agent |

**Kernel Session Lifecycle**:
- Created on first interactive edit for a job
- Bootstraps with dataset loading and common imports (CSV path passed via environment variable to prevent code injection)
- 30-minute idle TTL with automatic cleanup (background daemon)
- LRU eviction: when `MAX_SESSIONS` is reached, the oldest idle session is automatically evicted instead of raising an error
- Thread-safe via `threading.Lock`

### 6.2 Conversational Follow-Up Architecture

After notebook generation, users can ask follow-up questions in **Interactive Mode**. The system generates new cells, executes them, and persists the conversation.

**Follow-Up Flow**:
```
User types follow-up question in chat bar
    ↓
POST /api/v2/notebooks/{job_id}/ask
    Body: { question }
    ↓
Load conversation history from DB (conversation_messages)
    ↓
KernelSession.introspect() → capture live variable state
    ↓
FollowUpAgent.ask(question, df_context, kernel_context, history)
    ├─ Classifies question type (drill-down/what-if/comparison/explain)
    ├─ Generates 1-3 code cells + 1 markdown cell
    └─ Returns JSON: { summary, cells, question_type }
    ↓
For each code cell: KernelSession.execute(code)
    ├─ Captures stdout, stderr, display_data
    └─ Extracts base64 images
    ↓
Persist to DB: user message + assistant message (with executed cells)
    ↓
Response: { summary, cells: [{source, output, images}], conversation_length }
    ↓
Frontend appends to conversation thread with inline code + charts
```

**Key Components**:

| Component | Location | Purpose |
|-----------|----------|---------|
| `FollowUpAgent` | `src/agents/follow_up_agent.py` | LLM agent that generates new analysis cells from questions |
| `ConversationMessage` | `src/server/db/models.py` | DB model for persistent conversation history |
| `FollowUpChat` | `frontend/src/components/FollowUpChat.tsx` | Chat UI with history loading and inline cell rendering |
| `FOLLOW_UP_PROMPT` | `src/prompts.py` | System prompt with question classification and output format |
| `KernelSession.introspect()` | `src/services/kernel_session_manager.py` | Captures live kernel variable state for richer LLM context |

## 7. Deep Dive: Agent Implementation Details

### 7.1 Data Profiler Agent

**Location**: `src/agents/phase1/data_profiler.py`

**Purpose**: First agent in Phase 1. Analyzes raw CSV structure and determines column types using a hybrid LLM + heuristic approach.

**Implementation Strategy**:
- **Hybrid Type Detection**: Combines statistical analysis (pandas dtypes, unique ratios, null counts) with LLM reasoning for ambiguous cases
- **Sample-Based Analysis**: Reads first 1000 rows for performance, extracts representative samples
- **Pattern Recognition**: Identifies dates, IDs, categorical vs continuous features

**Key Outputs** (`ProfilerToCodeGenHandoff`):
```python
{
    "columns": [
        {
            "name": "Age",
            "detected_type": "numeric",
            "sample_values": [25, 30, 45, ...],
            "null_count": 12,
            "unique_count": 58,
            "suggested_operations": ["histogram", "describe"]
        },
        ...
    ],
    "row_count": 10000,
    "column_count": 15,
    "data_quality_issues": ["Missing values in 'Salary' (12%)"],
    "high_cardinality_columns": ["customer_id", "transaction_id"]
}
```

**Decision Logic**:
1. **Numeric Detection**: dtype check + numeric conversion test
2. **Categorical Detection**: unique_ratio < 0.05 OR dtype == 'object'
3. **Date Detection**: Regex patterns + pandas.to_datetime() success
4. **ID Detection**: unique_ratio > 0.90 OR column name contains 'id'

**Performance Optimizations**:
- Caches column statistics to avoid repeated computation
- Uses chunked reading for large files (>100MB)
- Parallel type detection for independent columns

---

### 7.2 Profile Code Generator Agent

**Location**: `src/agents/phase1/profile_codegen.py`

**Purpose**: Translates profiler's analysis plan into executable Jupyter notebook cells.

**Code Generation Strategy**:

**Cell Type 1: Setup & Imports**
```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
```

**Cell Type 2: Data Loading**
```python
df = pd.read_csv('{csv_path}')
print(f"Dataset Shape: {df.shape}")
df.head()
```

**Cell Type 3: Column-Specific Analysis**
- For numeric columns: `df['Age'].describe()`, `df['Age'].hist()`
- For categorical: `df['Category'].value_counts()`, bar charts
- For dates: Time series plots, temporal patterns

**Cell Type 4: Correlation Matrix** (only for numeric columns)
```python
numeric_cols = df.select_dtypes(include=[np.number]).columns
corr_matrix = df[numeric_cols].corr()
sns.heatmap(corr_matrix, annot=True, cmap='coolwarm')
```

**Cell Type 5: Missing Value Report**
```python
missing_data = df.isnull().sum()
missing_pct = (missing_data / len(df)) * 100
missing_df = pd.DataFrame({
    'Column': missing_data.index,
    'Missing Count': missing_data.values,
    'Missing %': missing_pct.values
}).sort_values('Missing Count', ascending=False)
```

**Quality Criteria**:
- All code must be PEP8 compliant (checked by validator)
- No hardcoded values except CSV path
- All visualizations must have titles and labels
- No string columns passed to numeric operations

---

### 7.3 Profile Validator Agent

**Location**: `src/agents/phase1/profile_validator.py`

**Purpose**: Executes generated code in sandbox, validates outputs, grants Profile Lock if quality >= 0.70.

**Validation Pipeline**:

**Stage 1: Static Analysis**
- PEP8 compliance check (line length, indentation, naming)
- Syntax validation via `ast.parse()`
- Import statement verification (only allow safe libraries)

**Stage 2: Sandbox Execution**
```python
# Create isolated namespace
namespace = {'__builtins__': safe_builtins}

# Execute each cell sequentially
for cell in notebook_cells:
    exec(cell.source, namespace)

# Verify expected variables exist
assert 'df' in namespace
assert isinstance(namespace['df'], pd.DataFrame)
```

**Stage 3: Output Validation**
- Check DataFrame loaded successfully
- Verify statistics match expected schema
- Ensure visualizations created (plt.gcf() not empty)
- Validate correlation matrix shape

**Stage 4: Quality Scoring**
```python
quality_score = (
    pep8_score * 0.30 +           # Code style
    execution_success * 0.40 +     # Runs without errors
    statistics_coverage * 0.20 +   # All columns analyzed
    visualization_quality * 0.10   # Plots created
)
```

**Profile Lock Grant Criteria**:
- `quality_score >= 0.70`
- No execution errors
- All required outputs present
- Data types correctly detected (>70% confidence)

**Enhanced Validation**:
- **Encoding Consistency**: Verifies one-hot, label, or ordinal encoding strategy is consistent
- **Performance Linting**: Detects anti-patterns (`.iterrows()`, excessive copying, inefficient loops)
- **PEP8 Scoring**: 6-point check (line length, whitespace, indentation, operator spacing, naming, imports)

---

### 7.4 Exploratory Conclusions Agent

**Location**: `src/agents/phase1/exploratory_conclusions.py`

**Purpose**: Synthesizes insights from locked profile using LLM, answers user's question without building models.

**Input Processing**:
```python
prompt_input = {
    "user_question": "What factors influence customer churn?",
    "data_summary": {
        "rows": 10000,
        "columns": 15,
        "quality_score": 0.85,
        "missing_values": "12% in Salary, 5% in Age"
    },
    "columns": [...],  # Full column profiles
    "correlations": {...},  # Correlation matrix
    "detected_patterns": [...]  # Anomalies, trends
}
```

**LLM Prompt Structure** (from `src/prompts.py`):
```
You are a data analyst. Given this data profile, answer the user's question:

USER'S QUESTION: {user_question}

DATA PROFILE:
- Rows: {row_count}
- Columns: {column_count}
- Quality Score: {quality_score}

COLUMN DETAILS:
{column_profiles}

KEY CORRELATIONS:
{correlation_matrix}

TASK:
1. Provide a direct answer to the question
2. List 3+ key findings grounded in actual data values
3. Provide statistical insights
4. Note data quality issues
5. Give 2+ actionable recommendations

OUTPUT FORMAT (JSON):
{
    "direct_answer": "...",
    "key_findings": [...],
    "statistical_insights": [...],
    "recommendations": [...],
    "confidence_score": 0.0-1.0
}
```

**Retry Logic with Fallback**:
- Max 3 attempts to parse LLM response
- If all attempts fail, generates fallback markdown with error details
- Caches results to avoid repeated slow failures

**Caching Strategy**:
- Cache key: `exploratory_conclusions_{md5(question)}`
- Stored per CSV hash to handle multiple questions on same dataset
- TTL: 7 days (same as profile cache)

**Quality Validation**:
- Direct answer addresses the question
- At least 3 key findings present
- Findings reference actual data values
- At least 2 actionable recommendations
- Confidence score >= 0.70

---

### 7.5 Strategy Agent (Phase 2)

**Location**: `src/agents/phase2/strategy.py`

**Purpose**: Consumes locked profile, analyzes target column, selects appropriate ML methodology.

**Decision Tree**:

```
Target Column Type Detection:
    ↓
Is Binary (2 unique values)?
    → Binary Classification
    → Models: LogisticRegression, RandomForest, XGBoost
    → Metrics: Accuracy, Precision, Recall, F1, ROC-AUC
    ↓
Is Multi-Class (3-20 unique values)?
    → Multi-Class Classification
    → Models: RandomForest, XGBoost, SVM
    → Metrics: Accuracy, F1 (macro), Confusion Matrix
    ↓
Is Continuous (numeric, >20 unique)?
    → Regression
    → Models: LinearRegression, RandomForest, GradientBoosting
    → Metrics: MAE, RMSE, R²
    ↓
No Target Column?
    → Clustering (fallback)
    → Models: KMeans, DBSCAN
    → Metrics: Silhouette Score, Inertia
```

**Feature Engineering Decisions**:
- **Numeric features**: StandardScaler, outlier clipping
- **Categorical features**: One-hot encoding (if cardinality < 10), Label encoding (otherwise)
- **Date features**: Extract year, month, day_of_week, is_weekend
- **High-cardinality IDs**: Drop entirely

**Output** (`StrategyToCodeGenHandoff`):
```python
{
    "task_type": "binary_classification",
    "target_column": "Churn",
    "feature_columns": ["Age", "Salary", "Tenure", ...],
    "dropped_columns": ["customer_id", "transaction_id"],
    "models_to_train": ["LogisticRegression", "RandomForest", "XGBoost"],
    "evaluation_metrics": ["accuracy", "precision", "recall", "roc_auc"],
    "train_test_split": 0.8,
    "cross_validation_folds": 5
}
```

---

### 7.6 Analysis Code Generator (Phase 2)

**Location**: `src/agents/phase2/analysis_codegen.py`

**Purpose**: Generates scikit-learn training code based on strategy.

**Generated Code Structure**:

**Cell 1: Preprocessing**
```python
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder

# Separate features and target
X = df.drop(columns=['Churn', 'customer_id'])
y = df['Churn']

# Encode categorical variables
le = LabelEncoder()
X['Gender'] = le.fit_transform(X['Gender'])

# Scale numeric features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Train/test split
X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y, test_size=0.2, random_state=42, stratify=y
)
```

**Cell 2: Model Training**
```python
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier

models = {
    'Logistic Regression': LogisticRegression(max_iter=1000),
    'Random Forest': RandomForestClassifier(n_estimators=100, random_state=42),
    'XGBoost': XGBClassifier(n_estimators=100, random_state=42)
}

results = {}
for name, model in models.items():
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    results[name] = {
        'accuracy': accuracy_score(y_test, y_pred),
        'precision': precision_score(y_test, y_pred),
        'recall': recall_score(y_test, y_pred)
    }
```

**Cell 3: Evaluation**
```python
from sklearn.metrics import classification_report, confusion_matrix

for name, model in models.items():
    print(f"\n{name} Results:")
    y_pred = model.predict(X_test)
    print(classification_report(y_test, y_pred))

    # Confusion Matrix
    cm = confusion_matrix(y_test, y_pred)
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
    plt.title(f'{name} - Confusion Matrix')
    plt.show()
```

**Cell 4: Feature Importance**
```python
# For tree-based models
for name in ['Random Forest', 'XGBoost']:
    importances = models[name].feature_importances_
    feature_names = X.columns

    plt.figure(figsize=(10, 6))
    plt.barh(feature_names, importances)
    plt.title(f'{name} - Feature Importance')
    plt.show()
```

---

### 7.7 Analysis Validator (Phase 2)

**Location**: `src/agents/phase2/analysis_validator.py`

**Purpose**: Validates ML code execution and model quality.

**Validation Checks**:

**1. Model Training Detection**
```python
# Check for .fit() calls in code
fit_calls = re.findall(r'\.fit\(', cell_source)
assert len(fit_calls) >= 1, "No model training detected"
```

**2. Metric Computation**
```python
# Verify evaluation metrics are calculated
required_metrics = ['accuracy', 'precision', 'recall']
for metric in required_metrics:
    assert metric in namespace, f"Missing metric: {metric}"
```

**3. Results Visualization**
```python
# Check for confusion matrix, ROC curve, or feature importance plots
assert 'confusion_matrix' in cell_source or 'roc_curve' in cell_source
```

**4. Model Performance Threshold**
```python
# Minimum acceptable accuracy/R² for validation to pass
if task_type == 'classification':
    min_accuracy = 0.60
    assert namespace['accuracy'] >= min_accuracy
elif task_type == 'regression':
    min_r2 = 0.50
    assert namespace['r2_score'] >= min_r2
```

**Quality Scoring**:
```python
quality_score = (
    code_quality * 0.25 +         # PEP8, syntax
    execution_success * 0.30 +    # Runs without errors
    model_performance * 0.30 +    # Accuracy/R² meets threshold
    visualization_quality * 0.15  # Plots generated
)
```

**Recursion Logic**:
- If `quality < 0.70`: Send feedback to Analysis CodeGen
- Feedback includes specific issues (e.g., "Model accuracy too low", "Missing confusion matrix")
- Max 4 recursion attempts (configurable in settings)

---

## 8. Live Notebook Execution

### 8.1 Architecture Overview

The system provides **Live Notebook Execution**, allowing users to execute generated Jupyter notebooks directly in the browser without leaving the Inzyts interface.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Live Notebook Execution Flow                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Browser (React Frontend)                                            │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Notebook Viewer Component                                     │   │
│  │  ├── Cell Renderer (Markdown + Code)                          │   │
│  │  ├── Execution Controls (Run Cell, Run All, Stop)             │   │
│  │  └── Output Display (stdout, plots, errors)                   │   │
│  └──────────────────────┬───────────────────────────────────────┘   │
│                         │ WebSocket                                  │
│                         ↓                                            │
│  FastAPI Backend (Port 8000)                                        │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ /api/v2/notebooks/{job_id}/ws/{kernel_id}                     │   │
│  │  └── WebSocket Proxy Handler                                  │   │
│  └──────────────────────┬───────────────────────────────────────┘   │
│                         │                                            │
│                         ↓                                            │
│  JupyterService (src/server/services/jupyter_proxy.py)              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ • Kernel Management (create, destroy, list)                   │   │
│  │ • Request Proxying (GET/POST to Jupyter Server)               │   │
│  │ • WebSocket Relay (bidirectional message forwarding)          │   │
│  │ • Health Monitoring (status checks, connection state)         │   │
│  └──────────────────────┬───────────────────────────────────────┘   │
│                         │ HTTP/WebSocket                             │
│                         ↓                                            │
│  Jupyter Server (Docker Container, Port 8888)                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ • Kernel Gateway (Python 3 kernels)                           │   │
│  │ • Cell Execution Engine                                       │   │
│  │ • Output Capture (stdout, stderr, display_data)               │   │
│  │ • Token Authentication (inzyts-token)                         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.2 JupyterService Implementation

**Location**: `src/server/services/jupyter_proxy.py`

**Purpose**: Acts as a proxy between the FastAPI backend and the Jupyter Server, managing kernel lifecycle and relaying WebSocket messages.

**Key Methods**:

```python
class JupyterService:
    def __init__(self, base_url="http://jupyter:8888", token="inzyts-token"):
        """Initialize with Jupyter Server URL and authentication token."""
        self.base_url = base_url
        self.token = token
        self.headers = {"Authorization": f"token {token}"}

    async def get_status(self) -> dict:
        """Check Jupyter Server health and availability."""
        # Returns: {"status": "healthy", "started": "...", "kernels": N}
        # Or: {"status": "unreachable", "error": "..."}

    async def create_kernel(self, kernel_name="python3") -> str:
        """Create a new Jupyter kernel and return its ID."""
        # POST /api/kernels → Returns kernel_id

    async def proxy_request(self, method: str, path: str, body=None) -> dict:
        """Proxy HTTP requests to Jupyter Server."""
        # Forwards GET/POST/DELETE to Jupyter API

    async def proxy_websocket(self, websocket: WebSocket, kernel_id: str):
        """Relay WebSocket messages between client and kernel."""
        # Bidirectional message forwarding for execute_request/reply
```

**Singleton Instance**:
```python
# Global instance for use across the application
jupyter_service = JupyterService()
```

### 8.3 API Endpoints

**Location**: `src/server/routes/notebooks.py`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v2/notebooks/{job_id}/html` | GET | Convert job's notebook to HTML for rendering |
| `/api/v2/notebooks/{job_id}/session` | POST | Create live Jupyter kernel session |
| `/api/v2/notebooks/{job_id}/ws/{kernel_id}` | WebSocket | Live kernel communication channel |

**Endpoint Details**:

**1. Get Notebook HTML**
```python
@router.get("/{job_id}/html")
async def get_notebook_html(job_id: str, db: Session):
    """
    Retrieve the generated notebook and convert to HTML.

    Returns: {"html": "<rendered_html>", "job_id": "..."}
    Errors:
      - 404: Job not found or no notebook generated
      - 500: Failed to render notebook
    """
```

**2. Create Live Session**
```python
@router.post("/{job_id}/session")
async def create_live_session(job_id: str, db: Session):
    """
    Start a live Jupyter kernel for interactive execution.

    Returns: {"job_id": "...", "kernel_id": "...", "status": "ready"}
    Errors:
      - 503: Jupyter Service unavailable
      - 500: Failed to create kernel
    """
```

**3. WebSocket Endpoint**
```python
@router.websocket("/{job_id}/ws/{kernel_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str, kernel_id: str):
    """
    Proxy WebSocket messages to/from Jupyter kernel.

    Message Types (Jupyter Protocol):
      - execute_request: Run cell code
      - execute_reply: Execution result
      - stream: stdout/stderr output
      - display_data: Rich output (plots, HTML)
      - error: Execution errors
    """
```

### 8.4 WebSocket Communication Protocol

**Message Flow**:
```
Client                  FastAPI                 Jupyter Server
  │                        │                          │
  │ ── connect ──────────→ │                          │
  │                        │ ── ws connect ─────────→ │
  │                        │ ←── ws accept ────────── │
  │ ←── accept ─────────── │                          │
  │                        │                          │
  │ ── execute_request ──→ │                          │
  │                        │ ── execute_request ───→ │
  │                        │ ←── busy ─────────────── │
  │ ←── busy ────────────── │                          │
  │                        │ ←── stream (stdout) ──── │
  │ ←── stream ──────────── │                          │
  │                        │ ←── display_data ─────── │
  │ ←── display_data ────── │                          │
  │                        │ ←── execute_reply ────── │
  │ ←── execute_reply ───── │                          │
  │                        │ ←── idle ─────────────── │
  │ ←── idle ────────────── │                          │
```

**WebSocket URL Construction**:
```python
# HTTP base URL → WebSocket URL
ws_url = base_url.replace('http', 'ws')
kernel_ws_url = f"{ws_url}/api/kernels/{kernel_id}/channels?token={token}"
```

### 8.5 Docker Compose Configuration

**Network Isolation**: Services are divided across two Docker networks:
- `backend` — connects frontend, backend, worker, jupyter, redis
- `db` — connects backend, worker, and PostgreSQL only

Database and Redis ports are bound to `127.0.0.1` to prevent external access. All services have memory limits enforced via `deploy.resources.limits`.

**Jupyter Service**:
```yaml
# docker-compose.yml
services:
  jupyter:
    image: jupyter/base-notebook:latest
    container_name: inzyts-jupyter
    environment:
      # JUPYTER_TOKEN must be set in .env — no default, compose fails if missing
      - JUPYTER_TOKEN=${JUPYTER_TOKEN:?JUPYTER_TOKEN must be set in .env}
      - JUPYTER_ENABLE_LAB=yes
    ports:
      - "8888:8888"
    volumes:
      - ./notebooks:/home/jovyan/notebooks
      - ./outputs:/home/jovyan/outputs
    networks:
      - backend
    deploy:
      resources:
        limits:
          memory: 2G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8888/api/status"]
      interval: 30s
      timeout: 10s
      retries: 3
```

**Backend healthcheck**: The FastAPI backend includes a healthcheck (`curl -f http://localhost:8000/health`). The frontend container uses `depends_on: condition: service_healthy` to wait for the backend before starting.

### 8.6 Error Handling

**JupyterService Errors**:
- **Connection Refused**: Returns `{"status": "unreachable", "error": "..."}` for graceful degradation
- **Kernel Creation Failed**: Raises exception, caught by API endpoint (500 response)
- **WebSocket Disconnect**: Closes connection with code 1011 (internal error)
- **Timeout**: AsyncIO timeout handling for unresponsive kernels

**API Error Responses**:
```python
# 404 - Job/Notebook not found
{"detail": "Job not found"}
{"detail": "No notebook generated for this job yet"}

# 503 - Jupyter Service unavailable
{"detail": "Jupyter Service unavailable"}

# 500 - Internal error (generic — internal details logged server-side only)
{"detail": "Failed to render notebook"}
{"detail": "Failed to create live session"}
{"detail": "Failed to read file preview"}
```

---

## 9. Multi-File Support & Template System

### 9.1 Multi-File CSV Support Architecture

The system provides comprehensive multi-file analysis capabilities, allowing users to load multiple CSV files and automatically detect join relationships.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Multi-File Loading Flow                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  User Input                                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Multiple CSV Files                                            │   │
│  │  ├── customers.csv                                            │   │
│  │  ├── orders.csv                                               │   │
│  │  └── products.csv                                             │   │
│  └──────────────────────┬───────────────────────────────────────┘   │
│                         │                                            │
│                         ↓                                            │
│  DataLoader Service (src/services/data_loader.py)                   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ • Load multiple CSVs into DataFrames                          │   │
│  │ • Profile each file independently                             │   │
│  │ • Merge files based on detected/specified joins               │   │
│  └──────────────────────┬───────────────────────────────────────┘   │
│                         │                                            │
│                         ↓                                            │
│  JoinDetector Service (src/services/join_detector.py)               │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ • Analyze column names for join candidates                    │   │
│  │ • Check value overlap between columns                         │   │
│  │ • Score and rank potential join relationships                 │   │
│  │ • Support multiple join strategies (inner, left, outer)       │   │
│  └──────────────────────┬───────────────────────────────────────┘   │
│                         │                                            │
│                         ↓                                            │
│  Output: Merged DataFrame + Join Metadata                           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.2 DataLoader Service

**Location**: `src/services/data_loader.py`

**Purpose**: Handles loading multiple CSV files and merging them based on detected or specified join relationships.

**File Format Support**:
- `.csv` - Loaded via `load_csv_robust()` with automatic delimiter/encoding detection
- `.parquet` - Loaded via `pd.read_parquet()`
- `.log` - Loaded via `load_csv_robust()` (auto-detects delimiter)

**Key Methods**:

```python
class DataLoader:
    def load_dataset(self, file_path: str) -> pd.DataFrame:
        """Load a dataset file into a DataFrame. Supports: .csv, .parquet, .log.
        Uses load_csv_robust() for CSV/log files with auto-delimiter detection."""

    def detect_joins(self, file_paths: List[str]) -> List[JoinCandidate]:
        """Detect potential join keys between files based on column names.
        Returns a list of candidate joins sorted by confidence."""

    def merge_datasets(self, multi_file_input: MultiFileInput) -> Tuple[pd.DataFrame, MergedDataset]:
        """Execute the merge plan defined in MultiFileInput.
        Returns the merged DataFrame and the MergedDataset metadata."""
```

**Input Model** (`src/models/multi_file.py`):
```python
class CSVFileInput(BaseModel):
    path: str
    alias: Optional[str] = None  # Short name for the file
    encoding: str = "utf-8"

class JoinStrategy(BaseModel):
    left_table: str
    right_table: str
    left_column: str
    right_column: str
    join_type: Literal["inner", "left", "right", "outer"] = "inner"
```

### 9.3 JoinDetector Service

**Location**: `src/services/join_detector.py`

**Purpose**: Automatically detects potential join relationships between DataFrames based on column names and value overlap.

**Detection Algorithm**:

1. **Name Matching**: Find columns with similar names across tables
   - Exact match: `customer_id` == `customer_id` (score: 1.0)
   - Suffix match: `id` in `orders` ↔ `customer_id` in `customers` (score: 0.8)
   - Pattern match: `cust_id` ↔ `customer_id` (score: 0.6)

2. **Value Overlap Analysis**: Check if column values actually match
   - High overlap (>80%): Strong join candidate
   - Medium overlap (50-80%): Possible join with data quality issues
   - Low overlap (<50%): Unlikely join, may indicate incorrect detection

3. **Cardinality Analysis**: Determine relationship type
   - One-to-One: Unique values on both sides
   - One-to-Many: Unique on left, duplicates on right
   - Many-to-Many: Duplicates on both sides (may need junction table)

**Key Methods**:

```python
class JoinDetector:
    def detect_joins(
        self,
        dataframes: Dict[str, pd.DataFrame]
    ) -> List[JoinCandidate]:
        """Detect potential join relationships between DataFrames."""
        # Returns ranked list of join candidates

    def score_join_candidate(
        self,
        df1: pd.DataFrame,
        df2: pd.DataFrame,
        col1: str,
        col2: str
    ) -> float:
        """Calculate confidence score for a potential join."""
        # Returns score 0.0 - 1.0

    def get_best_joins(
        self,
        candidates: List[JoinCandidate],
        max_joins: int = 3
    ) -> List[JoinCandidate]:
        """Select the best non-conflicting joins."""
        # Avoids duplicate table pairs, returns top candidates
```

**Output Model**:
```python
class JoinCandidate(BaseModel):
    left_table: str
    right_table: str
    left_column: str
    right_column: str
    confidence: float  # 0.0 - 1.0
    overlap_ratio: float
    suggested_join_type: str
    cardinality: str  # "one-to-one", "one-to-many", "many-to-many"
```

### 9.4 Domain Template System

**Location**: `src/services/template_manager.py`

**Purpose**: Manages domain-specific analysis templates that provide pre-configured settings, column mappings, and analysis patterns for specific industries or use cases.

**Template Structure** (`src/models/templates.py`):
```python
class DomainTemplate(BaseModel):
    domain_name: str  # e.g., "retail", "healthcare", "finance"
    version: str
    description: str

    # Column mapping rules
    column_mappings: Dict[str, ColumnMapping]

    # Default analysis settings
    default_mode: PipelineMode
    suggested_questions: List[str]

    # Domain-specific validations
    required_columns: List[str]
    column_constraints: Dict[str, ColumnConstraint]

    # Visualization preferences
    chart_preferences: Dict[str, str]

class ColumnMapping(BaseModel):
    standard_name: str  # Canonical column name
    aliases: List[str]  # Alternative names to match
    data_type: str
    description: str
    business_context: str
```

**Key Methods**:

```python
class TemplateManager:
    def __init__(self, templates_dir: str = "templates/"):
        """Initialize with templates directory path."""

    def get_all_templates(self) -> List[DomainTemplate]:
        """List all available domain templates."""

    def get_template(self, domain_name: str) -> Optional[DomainTemplate]:
        """Get a specific template by domain name."""

    def save_template(self, template: DomainTemplate) -> bool:
        """Save a new or updated template."""

    def delete_template(self, domain_name: str) -> bool:
        """Delete a template by domain name."""

    def apply_template(
        self,
        df: pd.DataFrame,
        template: DomainTemplate
    ) -> Tuple[pd.DataFrame, Dict[str, str]]:
        """Apply template column mappings to DataFrame."""
        # Returns renamed DataFrame and mapping log
```

**API Endpoints** (`src/server/routes/templates.py`):

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v2/templates` | GET | List all available templates |
| `/api/v2/templates` | POST | Upload new template (JSON file) |
| `/api/v2/templates/{domain_name}` | DELETE | Delete a template |

### 9.5 Data Dictionary Integration

**Location**: `src/services/dictionary_manager.py`

**Purpose**: Parses and applies data dictionaries to enhance column understanding with business context, value mappings, and validation rules.

**Dictionary Structure** (`src/models/dictionary.py`):
```python
class DataDictionary(BaseModel):
    name: str
    version: str
    columns: Dict[str, ColumnDefinition]

class ColumnDefinition(BaseModel):
    description: str
    data_type: str
    business_meaning: str
    valid_values: Optional[List[str]] = None
    value_mappings: Optional[Dict[str, str]] = None  # e.g., {"1": "Active", "0": "Inactive"}
    constraints: Optional[ColumnConstraint] = None
    related_columns: Optional[List[str]] = None
```

**Key Methods**:

```python
class DictionaryManager:
    def parse_dictionary(self, file_path: str) -> DataDictionary:
        """Parse a data dictionary from CSV, JSON, or Excel."""

    def apply_dictionary(
        self,
        df: pd.DataFrame,
        dictionary: DataDictionary
    ) -> pd.DataFrame:
        """Apply value mappings and constraints to DataFrame."""

    def generate_profile_context(
        self,
        dictionary: DataDictionary
    ) -> str:
        """Generate context string for LLM prompts."""
        # Returns formatted business context for profiler

    def validate_against_dictionary(
        self,
        df: pd.DataFrame,
        dictionary: DataDictionary
    ) -> List[ValidationIssue]:
        """Check DataFrame against dictionary constraints."""
```

### 9.6 Parameter Tuning Codegen

**Purpose**: Generates hyperparameter tuning code for machine learning models, integrated into the Phase 2 predictive pipeline.

**Configuration Model** (`src/models/tuning.py`):
```python
class TuningConfig(BaseModel):
    method: Literal["grid_search", "random_search", "optuna"] = "grid_search"
    cv_folds: int = 5
    scoring: str = "accuracy"  # or "f1", "roc_auc", "rmse"
    n_iter: Optional[int] = None  # For random search
    param_grids: Dict[str, Dict[str, List[Any]]]
```

**Generated Code Example**:
```python
# Generated by TuningCodegen Agent
from sklearn.model_selection import GridSearchCV

param_grid = {
    'n_estimators': [50, 100, 200],
    'max_depth': [5, 10, 15, None],
    'min_samples_split': [2, 5, 10]
}

grid_search = GridSearchCV(
    estimator=RandomForestClassifier(random_state=42),
    param_grid=param_grid,
    cv=5,
    scoring='accuracy',
    n_jobs=-1,
    verbose=1
)

grid_search.fit(X_train, y_train)

print(f"Best Parameters: {grid_search.best_params_}")
print(f"Best Score: {grid_search.best_score_:.4f}")

best_model = grid_search.best_estimator_
```

### 9.7 Exclude Columns Feature

**Purpose**: Allows users to filter out specific columns from the analysis pipeline, useful for removing PII (Personally Identifiable Information), high-cardinality IDs, or irrelevant features that might confuse the LLM or skew models.

**Implementation**:
- **Input**: `exclude_columns` list passed via API/CLI
- **Orchestration**: Passed to `AnalysisState` and propagated to Agents
- **Phase 1 (Profiler)**: Columns are dropped from DataFrame *before* profiling statistics are generated
- **Phase 1 (Conclusions)**: Excluded columns are not visible to the LLM for insight generation
- **Phase 2 (Strategy)**: Excluded columns are not available for feature selection

---

### 9.8 Data Quality Remediation

**Purpose**: Automatically detect data quality issues and generate remediation code, enabling side-by-side comparison of original vs. remediated data analysis.

**Quality Issue Types** (`QualityIssueType` enum):
- **Missing Values**: Null/NaN detection with percentage thresholds
- **Outliers (IQR)**: Values outside 1.5 × IQR range
- **Outliers (Z-Score)**: Values with |z| > 3
- **Duplicate Rows**: Exact row duplicates
- **Duplicate Keys**: Primary key violations
- **Type Mismatch**: Columns with mixed types
- **High Cardinality**: Categorical columns with >95% unique values
- **Infinite Values**: Numeric columns containing ±∞
- **Whitespace Issues**: Leading/trailing spaces in strings

**Remediation Types** (`RemediationType` enum):
- **Imputation**: Mean, median, mode, constant, KNN, forward/backward fill
- **Outlier Handling**: Cap/floor (IQR, percentile, z-score), winsorize, log transform, drop, flag
- **Duplicate Handling**: Drop (keep first/last/none), flag
- **Type Coercion**: Convert to numeric, datetime, string

**Safety Rating System** (`SafetyRating` enum):
```python
class SafetyRating(str, Enum):
    SAFE = "safe"           # Auto-apply recommended
    REVIEW = "review"       # Requires user review
    RISKY = "risky"         # Significant data modification
    DANGEROUS = "dangerous" # Major data loss potential
```

**Configuration Model** (`src/models/handoffs.py`):
```python
class RemediationPlan(BaseModel):
    issue: QualityIssue           # Detected quality issue
    remediation_type: RemediationType
    remediation_params: Dict[str, Any]
    safety_rating: SafetyRating
    safety_rationale: str
    auto_apply_recommended: bool
    user_approved: Optional[bool]
    user_override_type: Optional[RemediationType]
    code_snippet: str             # Executable pandas code
    code_explanation: str
    estimated_rows_affected: int
    estimated_data_loss: float    # 0.0 - 1.0
```

**Dual-Path Analysis**:
When remediation is applied, the notebook generates side-by-side comparison:
1. **Path A (Original)**: Analysis on raw data with quality issues noted
2. **Path B (Remediated)**: Analysis on cleaned data with remediation audit trail

---

### 9.9 Dimensionality Reduction Mode

**Purpose**: Dedicated pipeline mode for PCA/t-SNE analysis with automatic assessment of when dimensionality reduction is beneficial.

**Mode Detection Keywords**:
- "dimensionality", "dim", "pca", "principal component"
- "reduce dimensions", "reduce features", "feature reduction"
- "t-sne", "tsne", "compress features"

**PCA Configuration Model** (`PCAConfig`):
```python
class PCAConfig(BaseModel):
    enabled: bool = True
    feature_count_threshold: int = 20  # Trigger PCA if > 20 features
    correlation_threshold: float = 0.9  # High multicollinearity
    variance_retention_target: float = 0.95  # 95% variance retained
    min_components: int = 2
    max_components: Optional[int] = None
    # Visualizations
    generate_2d_plot: bool = True
    generate_3d_plot: bool = True
    generate_scree_plot: bool = True
    generate_loadings_heatmap: bool = True
    explain_top_n_components: int = 5
    show_feature_contributions: bool = True
    # Behavior
    apply_to_training_only: bool = True
    use_llm_decision: bool = True
```

**DimensionalityStrategyAgent**:
- **Input**: ProfileToStrategyHandoff with PCAConfig
- **Output**: DimensionalityStrategyHandoff with component recommendations
- **Features**:
  - Automatic variance analysis to determine optimal n_components
  - Scree plot generation with elbow detection
  - Feature loading interpretation per component
  - 2D and 3D projections with cluster coloring (if target available)
  - Loadings heatmap showing feature-component relationships

**Generated Notebook Structure**:
```
1. Setup & Imports (sklearn.decomposition.PCA)
2. Data Loading (with standardization)
3. PCA Fit & Transform
4. Scree Plot (eigenvalues vs. components)
5. Cumulative Variance Plot
6. Component Loadings Analysis
7. 2D Projection Scatter Plot
8. (Optional) 3D Projection
9. Feature Importance by Component
10. Conclusions & Recommendations
```

---

### 9.10 PCA Assessment

**Purpose**: Automatically evaluate when dimensionality reduction should be recommended based on dataset characteristics.

**Assessment Criteria**:
1. **Feature Count**: > 20 numeric features triggers assessment
2. **Multicollinearity**: Correlation matrix with |r| > 0.9 pairs
3. **Variance Distribution**: Features with very low variance
4. **LLM Decision**: Optional LLM-based assessment for borderline cases

**Implementation** (`DataProfilerAgent.assess_pca_applicability()`):
```python
def assess_pca_applicability(self, df: pd.DataFrame) -> Optional[PCAConfig]:
    numeric_cols = df.select_dtypes(include=[np.number]).columns

    # Threshold check: > 20 numeric features
    if len(numeric_cols) <= 20:
        return None

    # Return PCA config if applicable
    return PCAConfig(
        enabled=True,
        feature_count_threshold=20,
        variance_retention_target=0.95,
        use_llm_decision=True
    )
```

**Integration Points**:
- **Phase 1 Profiler**: Calls `assess_pca_applicability()` during profiling
- **ProfilerToCodeGenHandoff**: Carries `pca_config` to code generation
- **Orchestrator**: Can trigger DIMENSIONALITY mode based on assessment

### 9.11 Cloud Storage Ingestion

**Location**: `src/server/services/cloud_ingestion.py`

**Purpose**: Downloads data files from cloud storage providers (AWS S3, Google Cloud Storage, Azure Blob Storage), validates them, converts to CSV if needed, and places them in the upload directory for downstream analysis.

**Supported Providers**:
| Provider | URI Schemes | SDK | Auth (env var) |
|----------|-------------|-----|----------------|
| AWS S3 | `s3://` | `boto3` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| Google Cloud Storage | `gs://` | `google-cloud-storage` | `GOOGLE_APPLICATION_CREDENTIALS` |
| Azure Blob Storage | `az://`, `abfs://`, `abfss://` | `azure-storage-blob` | `AZURE_STORAGE_CONNECTION_STRING` |

**Key Behaviors**:
*   URI scheme allowlist enforced — `http://`, `ftp://`, `file://` are rejected.
*   File size checked before download (`CLOUD_MAX_FILE_SIZE`, default 500 MB).
*   Automatic format conversion: JSON → CSV, Excel → CSV, Parquet → CSV. Plain CSV is passed through.
*   SDKs are imported lazily — no hard dependency on cloud SDKs at import time.

### 9.12 REST API Data Extraction

**Location**: `src/agents/api_agent.py`

**Purpose**: Fetches data from REST APIs, handles authentication and response parsing, extracts tabular data via JMESPath, and saves results as CSV.

**Authentication Modes**:
| Type | Config Fields | Header Generated |
|------|---------------|-----------------|
| Bearer | `type: "bearer"`, `token` | `Authorization: Bearer <token>` |
| API Key | `type: "api_key"`, `key_name`, `key_value` | `<key_name>: <key_value>` |
| Basic | `type: "basic"`, `username`, `password` | `Authorization: Basic <base64>` |

**Security**:
*   SSRF protection: all URLs resolved to IP and checked against private/reserved ranges (RFC 1918, link-local, multicast).
*   `localhost` and `127.0.0.1` explicitly allowed for development.
*   Response size capped at `API_MAX_RESPONSE_SIZE` (default 100 MB).
*   Request timeout: `API_TIMEOUT` (default 30 seconds).

**Data Extraction**:
*   JMESPath expressions for precise nested JSON extraction.
*   Auto-detection of common response keys (`data`, `results`, `items`, `records`).
*   Nested JSON flattened via `pd.json_normalize()`.

---

## 10. Error Handling & Recovery Strategies

### 10.1 Graceful Degradation

**Principle**: System should never crash; always provide useful output even if degraded.

**Strategy 1: Fallback Outputs**
- If LLM fails to generate conclusions after 3 attempts, create markdown cell explaining the failure
- If model training fails, generate descriptive statistics instead
- If visualization fails, output raw metrics as tables

**Strategy 2: Partial Success**
- If 2/3 models train successfully, proceed with the successful ones
- If 80% of columns are profiled correctly, continue with warning note

**Strategy 3: Cache Fallback**
- If CSV changed but cache exists, offer user choice: use stale cache or rerun
- If cache corrupted, log error and rerun Phase 1 automatically

---

### 10.2 Recursion Limits & Escalation

**Problem**: Infinite loops if validator keeps rejecting output.

**Solution**: Configurable recursion limits with escalation.

**Phase 1 Limits** (`src/config.py`):
```python
class Phase1Config:
    max_profile_codegen_recursions = 3
    escalation_threshold = 2
    fallback_on_max_recursions = True
```

**Escalation Logic**:
1. **Attempt 1**: Normal generation
2. **Attempt 2**: Include validator feedback in prompt
3. **Attempt 3**: Simplify requirements (e.g., skip optional visualizations)
4. **Max Reached**: Accept best attempt so far OR use fallback template

**Phase 2 Limits**:
```python
class Phase2Config:
    max_analysis_codegen_recursions = 4
    min_acceptable_quality = 0.70
    auto_simplify_after_attempts = 2  # Reduce model count or complexity
```

---

### 10.3 LLM Provider Failures

**Resilience Strategy**:

**1. Retry with Exponential Backoff**
```python
for attempt in range(max_retries):
    try:
        response = llm.invoke(prompt)
        break
    except Exception as e:
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)  # 1s, 2s, 4s
        else:
            raise
```

**2. Provider Fallback** (Future Enhancement)
```python
providers = ['anthropic', 'openai', 'ollama']
for provider in providers:
    try:
        return invoke_with_provider(provider, prompt)
    except Exception as e:
        logger.warning(f"Provider {provider} failed: {e}")
        continue
```

**3. Model Degradation**
```python
# If primary model fails, use smaller/faster model
models_by_priority = ['claude-opus-4-6', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001', 'gpt-4o']
```

---

### 10.4 Data Quality Issues

**Handling Strategies**:

**Issue 1: High Missing Value Percentage (>50%)**
- **Detection**: Data Profiler identifies during analysis
- **Action**: Flag column, suggest dropping or imputation
- **Output**: Warning in notebook: "Column 'X' has 65% missing values"

**Issue 2: All Values Unique (ID column)**
- **Detection**: `unique_ratio > 0.95`
- **Action**: Automatically drop from feature set in Phase 2
- **Output**: Note in strategy section: "Dropped high-cardinality columns: [...]"

**Issue 3: Data Type Ambiguity**
- **Detection**: LLM confidence < 0.7 for column type
- **Action**: Request user clarification (CLI prompt) or use conservative default (treat as object)
- **Output**: Warning: "Column 'Date' detected as string, attempted date parsing"

**Issue 4: Target Column Imbalance (>95% one class)**
- **Detection**: Strategy agent checks class distribution
- **Action**: Use stratified split, SMOTE oversampling, or warn user
- **Output**: "Severe class imbalance detected (98% class 0). Consider resampling."

---

## 11. Performance Optimization Strategies

### 11.1 Caching Hierarchy

**Level 1: Profile Cache** (7-day TTL)
- Location: `~/.Inzyts_cache/{csv_hash}/`
- Contains: ProfileLock, notebook cells, handoff objects
- Invalidation: CSV content change (SHA256 hash mismatch)

**Level 2: Exploratory Conclusions Cache** (7-day TTL)
- Location: `~/.Inzyts_cache/{csv_hash}/exploratory_conclusions_{question_hash}`
- Contains: Cached LLM-generated insights per question
- Invalidation: Question text change or profile cache invalidation
- Note: Conclusion cache lookup only occurs when `using_cached_profile` is True (fresh runs always generate new conclusions)

**Level 3: In-Memory State Cache** (session-only)
- LangGraph state persistence during execution
- Column statistics, intermediate results
- Cleared after notebook generation

---

### 11.2 Computational Efficiency

**Strategy 1: Lazy Loading**
- Only load necessary columns for profiling
- Use `pd.read_csv(usecols=[...])` when possible

**Strategy 2: Sampling**
- Profile first 10,000 rows for datasets >100K rows
- Validation note: "Profile based on sample of 10,000 rows"

**Strategy 3: Parallel Execution**
- Independent column profiling runs in parallel
- Multiple model training can be parallelized (future enhancement)

**Strategy 4: Code Generation Optimization**
- Reuse template cells with variable substitution instead of LLM generation for common patterns
- LLM only for complex/ambiguous cases

---

### 11.3 Token Usage Optimization

**Problem**: LLM API costs scale with token count.

**Solutions**:

**1. Prompt Compression**
- Summarize large DataFrames instead of passing full content
- Use column samples (5 values) instead of full unique lists

**2. Response Format Constraints**
- Use JSON mode / function calling for structured outputs
- Reduces token waste on verbose natural language

**3. Caching LLM Responses**
- Cache deterministic LLM calls (e.g., code generation for same column type)
- Reuse across similar datasets

**4. Selective LLM Usage**
- Use heuristics for obvious cases (e.g., dtype='int64' → numeric)
- Only invoke LLM for ambiguous type detection or strategic decisions

---

## 12. Security & Safety Considerations

### 12.1 Sandbox Execution

**Implementation**: `src/core/sandbox.py`

**Restrictions**:
- No file system access (except specified CSV path)
- No network requests
- No subprocess execution
- No module imports outside allowlist

**Allowlist**:
```python
SAFE_IMPORTS = [
    'pandas', 'numpy', 'matplotlib', 'seaborn',
    'sklearn', 'scipy', 'datetime', 'math'
]
```

**Execution Timeout**:
- Max 60 seconds per cell
- Prevents infinite loops

---

### 12.2 Input Validation

**CSV Path Validation** (`src/server/routes/analysis.py`):
- Must be relative to `UPLOAD_DIR` or `DATASETS_DIR` (resolved at module load)
- Resolved with `Path.resolve()` to normalise `..` sequences
- **Symlinks explicitly rejected** before resolution — a symlink inside the allowed directory could point anywhere on the filesystem
- `is_relative_to()` containment check after resolution
- File existence verified before queuing

**SQL Input Validation** (`src/agents/sql_agent.py`, `src/utils/db_utils.py`):
- URI scheme allowlist: `postgresql`, `mysql`, `mssql`, `bigquery`, `snowflake`, `redshift+redshift_connector`, `databricks+connector` — `sqlite://` explicitly blocked (could read `/etc/shadow` or other host files)
- `sqlglot` AST validation rejects any non-`SELECT` statement, including CTEs with embedded DML (e.g. `WITH x AS (DELETE FROM users) SELECT 1`)
- **Read-only transactions**: Database connections enforce `SET TRANSACTION READ ONLY` and use backend-specific read-only execution options (`postgresql_readonly`, `mysql_read_only`) as a defense-in-depth layer
- Row cap: `SQL_MAX_ROWS` env var (default 200,000) — first chunk only, iterator closed immediately
- **Column cap**: `SQL_MAX_COLS` env var (default 500) — guards against OOM from wide `SELECT *` results
- Rejected queries are logged at `WARNING` level with a 200-char preview for audit trails

**Cloud Storage Validation** (`src/server/services/cloud_ingestion.py`):
- URI scheme allowlist: `s3`, `gs`, `az`, `abfs`, `abfss` — `http`, `ftp`, `file` rejected
- File size checked before download to prevent resource exhaustion
- Credentials sourced exclusively from environment variables — never from user input or URIs

**REST API SSRF Protection** (`src/agents/api_agent.py`):
- All target URLs resolved to IP addresses via `socket.gethostbyname()`
- Checked against private/reserved ranges: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, link-local, multicast
- `localhost` and `127.0.0.1` explicitly allowed for development use
- Response size and timeout enforced to prevent denial-of-service

**User Question Sanitization**:
- Strip HTML/script tags
- Max length: 500 characters
- No file path injection attempts

---

### 12.3 Generated Code Safety

**Static Analysis Checks**:
- No `eval()` or `exec()` in generated code
- No `__import__()` or dynamic imports
- No file write operations
- No dangerous pandas operations (e.g., `df.to_sql()` without explicit user consent)

**Runtime Monitoring**:
- Memory usage tracking
- CPU usage limits
- Automatic termination if thresholds exceeded

---

### 12.4 Authentication & Transport

**JWT Authentication** (`src/server/middleware/auth.py`, `src/server/routes/auth.py`):
- `POST /api/v2/auth/login` authenticates with username + password, returns JWT with `sub` and `role` claims
- Passwords hashed with bcrypt; verified with `bcrypt.checkpw()`
- System API token (`INZYTS_API_TOKEN`) for Celery workers, verified with `secrets.compare_digest()` (constant-time)
- JWT tokens stored in `sessionStorage` only — never `localStorage` or compiled into the Vite bundle
- `ADMIN_PASSWORD` required — the server refuses to start without it
- First-boot admin auto-creation with race-safe `IntegrityError` handling
- `GET /api/v2/auth/me` returns current user profile (id, username, role)

**Rate Limiting** (`src/server/rate_limiter.py`):
- `POST /api/v2/analyze` — 10 requests/minute
- `GET /api/v2/jobs/{job_id}` — 30 requests/minute (also limits log-file reads)
- Implemented via `slowapi`; client IP read from `Request` object

---

### 12.5 Role-Based Access Control (RBAC)

**Implementation**: `src/server/middleware/auth.py`, `src/server/db/models.py`

**Role Hierarchy** (defined in `ROLE_HIERARCHY`):
```
Admin (level 2) > Analyst (level 1) > Viewer (level 0)
```

**Database Schema**:
- `UserRole` enum: `admin`, `analyst`, `viewer` (PostgreSQL native enum)
- `users.role` column with server default `viewer`
- Alembic migration auto-promotes existing `admin` username to `admin` role

**Enforcement** (`require_role()` dependency factory):
```python
@router.get("/admin-only")
async def admin_endpoint(user: User = Depends(require_role(UserRole.ADMIN))):
    ...
```
- Hierarchy-aware: `require_role(UserRole.ANALYST)` also admits admins
- Returns `403 Forbidden` with descriptive message on insufficient permissions
- Users with no role attribute default to `viewer` level
- System API tokens receive `admin` role for full access

**Admin Endpoints**:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v2/admin/users` | GET | List all users (paginated) |
| `/api/v2/admin/users` | POST | Create new user with role |
| `/api/v2/admin/users/{user_id}` | PUT | Update user (role, email, active, password) |
| `/api/v2/admin/users/{user_id}` | DELETE | Delete user (self-delete prevented) |
| `/api/v2/admin/audit-logs` | GET | Query audit logs (filter by user, action, date) |
| `/api/v2/admin/audit-logs/summary` | GET | Action counts grouped by type |

**Frontend Protection**:
- `AdminRoute` component redirects non-admin users
- Admin navigation links only rendered when `isAdmin()` is true
- Role and username persisted in `sessionStorage` alongside JWT token

---

### 12.6 Audit Logging

**Implementation**: `src/server/middleware/audit.py`, `src/server/db/models.py`

**AuditLog Table** (`audit_logs`):
- `timestamp` (DateTime, indexed), `user_id`, `username` (both indexed), `action` (indexed)
- `resource_type`, `resource_id`, `detail` (Text), `ip_address`, `status_code`, `method`, `path`

**Two Audit Paths**:
1. **AuditMiddleware** (automatic) — Starlette middleware that auto-logs requests to security-relevant paths (`/auth/`, `/analyze`, `/files/`, `/jobs/`, `/admin/`). Skips noisy GET-only endpoints. User identity extracted from `request.state.audit_user` (set by `verify_token` dependency).
2. **`record_audit()`** (manual) — Async helper called from route handlers for fine-grained control (e.g., failed login with username, user CRUD with change details).

**Action Classification** (`_classify_action()`):
- Maps HTTP method + path to: `login`, `login_failed`, `start_analysis`, `upload_file`, `cancel_job`, `create_user`, `update_user`, `delete_user`, `view_audit_logs`

**Resilience**: All DB exceptions caught and logged — audit failures never break the request flow.

---

### 12.7 Docker Hardening

**Non-root execution** (`Dockerfile`):
- `base` stage creates a `inzyts` system user (`--no-create-home --shell /bin/false`)
- `backend` stage: data directories (`data/uploads`, `logs`, `output`) are `chown`-ed to `inzyts` before `USER inzyts`
- Upload directory has restricted permissions (`chmod 750 data/uploads`)
- Both the FastAPI server and Celery worker run as `inzyts`, not root
- Jupyter target runs as `${NB_UID}` (jovyan), not root — pip installs done as non-root user

**Mandatory secrets** (`docker-compose.yml`):
- `POSTGRES_PASSWORD` uses `:?` syntax — compose fails at startup if the variable is unset (no silent `"postgres"` default)
- `JUPYTER_TOKEN` uses `:?` syntax on the `jupyter` service for the same reason
- `ADMIN_PASSWORD` is required (no default) — the settings model enforces this at startup

**Network isolation** (`docker-compose.yml`):
- Two separate networks: `backend` (frontend, backend, worker, jupyter, redis) and `db` (backend, worker, postgres)
- PostgreSQL port bound to `127.0.0.1:5432` — not accessible from outside the host
- Redis port bound to `127.0.0.1:6379` — not accessible from outside the host

**Resource limits**:
- All services have `deploy.resources.limits.memory` enforced (db: 1G, redis: 512M, backend/worker: 4G, jupyter: 2G, frontend: 512M)
- Restart policy: `on-failure:5` (prevents infinite restart loops)

**Health checks**:
- Backend: `curl -f http://localhost:8000/health` (interval: 30s)
- Frontend `depends_on` uses `condition: service_healthy` to wait for backend readiness

**Credential masking** (`src/server/services/engine.py`):
- Log messages emitted to WebSocket clients are automatically scrubbed of database URI credentials (`user:pass@host`) and API keys/tokens via regex patterns

---

## 13. Monitoring & Observability

### 13.1 Structured Logging

**Implementation**: `src/utils/logger.py`

**Log Levels**:
- **INFO**: Normal operations (agent invocations, phase transitions)
- **WARNING**: Degraded performance (low confidence, cache mismatches)
- **ERROR**: Failures requiring attention (validation failures, LLM errors)

**Key Log Events**:
```python
# Pipeline Mode Events
logger.mode_detected("exploratory", reason="keyword_match")
logger.mode_explicit("predictive")

# Cache Events
logger.cache_hit(csv_hash, age_days=2)
logger.cache_miss(csv_hash)
logger.cache_expired(csv_hash, age_days=8)
logger.cache_saved(csv_hash)

# Agent Execution Events
logger.agent_execution("DataProfiler", "invoked")
logger.agent_execution("ProfileValidator", "completed", quality=0.85)
logger.agent_execution("ExploratoryConclusionsAgent", "failed", reason="parse_error")

# Validation Events
logger.validation_passed("profile", quality=0.85)
logger.validation_failed("analysis", quality=0.62, reason="low_accuracy")

# Performance Events
logger.log_token_usage("ExploratoryConclusionsAgent", tokens=1250, model="claude-sonnet-4-6")
logger.log_execution_time("Phase1", duration_seconds=45.2)
```

---

### 13.2 Metrics Collection

**Proposed Metrics**:
- Average execution time per phase
- Token usage per agent
- Cache hit rate
- Recursion trigger frequency
- User satisfaction scores (via feedback)

**Storage**: Prometheus + Grafana dashboard

---

## 14. Testing Strategy

### 14.1 Test Coverage

The system includes comprehensive test coverage with **770+ tests** across **52 test files** achieving ~95% coverage.

**Unit Tests** (`tests/unit/`):
- Individual agent process() methods
- Cache manager operations
- Validator quality scoring logic
- Mode inference keyword detection (7-mode)
- Data quality remediation logic
- Dimensionality reduction assessment

**Integration Tests** (`tests/integration/`):
- Full Phase 1 pipeline (Profiler → CodeGen → Validator)
- Full Phase 2 pipeline (Strategy → CodeGen → Validator)
- Cache save/restore workflow
- Multi-file join detection

**End-to-End Tests** (`tests/e2e/`):
- Complete exploratory workflow (CSV → Notebook)
- Complete predictive workflow with cache
- Upgrade workflow (exploratory → predictive)
- All 7 pipeline modes

**Web API Tests** (`tests/server/`):
- All FastAPI endpoints (`/api/v2/analyze`, `/api/v2/jobs`, etc.)
- Background job management
- Cache check integration
- WebSocket communication
- Notebook API endpoints

**Service Tests** (`tests/services/`):
- JupyterService proxy tests
- Template manager tests
- Join detector tests
- Data loader tests

---

### 14.2 Test Fixtures

**Sample Datasets** (`tests/fixtures/`):
- `iris.csv` - Clean, small classification dataset
- `Bank_Churn.csv` - Real-world churn prediction dataset with missing values
- `synthetic_large.csv` - Performance testing (100K+ rows)
- `titanic.csv` - Binary classification benchmark
- `housing.csv` - Regression benchmark

**Mock Components**:
- Mock LLM responses for deterministic testing
- Mock cache manager for isolated unit tests
- Mock sandbox for validation testing
- Mock JupyterService for notebook execution tests

---

## 15. Production Deployment Architecture

### 15.1 Full Stack Deployment

```
                        ┌─────────────────────────────────┐
                        │     Load Balancer (Nginx)       │
                        │     - SSL Termination           │
                        │     - Rate Limiting             │
                        └────────────┬────────────────────┘
                                     │
                        ┌────────────┴────────────┐
                        │                         │
                        ↓                         ↓
              ┌──────────────────┐      ┌──────────────────┐
              │  FastAPI Server  │      │  FastAPI Server  │
              │  (Instance 1)    │      │  (Instance 2)    │
              │  Port 8000       │      │  Port 8001       │
              └────────┬─────────┘      └─────────┬────────┘
                       │                           │
                       └──────────┬────────────────┘
                                  │
                   ┌──────────────┴──────────────┐
                   │                             │
                   ↓                             ↓
         ┌──────────────────┐          ┌──────────────────┐
         │   PostgreSQL     │          │     Redis        │
         │   (Primary)      │          │   (Cache/Queue)  │
         │   Port 5432      │          │   Port 6379      │
         └──────────────────┘          └──────────────────┘
                   │
                   ↓
         ┌──────────────────┐
         │  Celery Workers  │
         │  (3-5 instances) │
         │  + Flower Monitor│
         └──────────────────┘
                   │
                   ↓
         ┌──────────────────┐
         │  React Frontend  │
         │  (Nginx Static)  │
         │  Port 5173       │
         └──────────────────┘
```

### 15.2 Environment Variables Reference

```bash
# Core Configuration
ENVIRONMENT=production  # development, staging, production
DEBUG=false
SECRET_KEY=<random-256-bit-key>

# Database (PostgreSQL)
DATABASE_URL=postgresql://user:password@host:5432/inzyts
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# Cache (Redis)
REDIS_URL=redis://host:6379/0
REDIS_MAX_CONNECTIONS=50

# LLM Providers
ANTHROPIC_API_KEY=sk-ant-xxxxx  # Primary provider
OPENAI_API_KEY=sk-xxxxx         # Fallback
GOOGLE_API_KEY=xxxxx            # Fallback
LLM_PROVIDER=anthropic          # Default provider
LLM_MODEL=claude-sonnet-4-6

# Cache System
CACHE_DIR=/var/cache/inzyts
CACHE_TTL_DAYS=7
CACHE_MAX_SIZE_GB=50

# Celery Workers
CELERY_BROKER_URL=redis://host:6379/1
CELERY_RESULT_BACKEND=redis://host:6379/2
CELERY_WORKER_CONCURRENCY=4
CELERY_TASK_TIME_LIMIT=3600  # 1 hour max per task

# Security
CORS_ORIGINS=https://app.daagent.com,https://daagent.com
API_RATE_LIMIT=100/hour
MAX_UPLOAD_SIZE_MB=500
# SQL agent limits
SQL_MAX_ROWS=200000   # Max rows returned by autonomous SQL agent
SQL_MAX_COLS=500      # Max columns — guards against wide SELECT * OOM

# Monitoring
SENTRY_DSN=https://xxxxx@sentry.io/xxxxx
LOG_LEVEL=INFO
METRICS_ENABLED=true
```

### 15.3 Startup Script (`start_app.sh`)

The production deployment uses a unified startup script that orchestrates all services:

```bash
#!/bin/bash
# start_app.sh - Unified application startup

set -e

echo "🚀 Starting Inzyts..."

# Step 1: Start Docker services (PostgreSQL, Redis, Frontend)
echo "📦 Starting Docker Compose services..."
docker-compose up -d postgres redis frontend

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL..."
until docker-compose exec -T postgres pg_isready -U postgres; do
  sleep 2
done

# Step 2: Run database migrations
echo "🗄️ Running Alembic migrations..."
alembic upgrade head

# Step 3: Start Celery workers in background
echo "⚙️ Starting Celery workers..."
celery -A src.server.celery_app worker --loglevel=info --concurrency=4 &
CELERY_PID=$!

# Step 4: Start Flower monitoring (optional)
echo "🌸 Starting Flower monitoring..."
celery -A src.server.celery_app flower --port=5555 &
FLOWER_PID=$!

# Step 5: Start FastAPI backend
echo "🌐 Starting FastAPI server..."
uvicorn src.server.main:app --host 0.0.0.0 --port 8000 --workers 2 &
BACKEND_PID=$!

# Wait for services to be healthy
sleep 5

echo "✅ All services started successfully!"
echo "   - Frontend: http://localhost:5173"
echo "   - Backend API: http://localhost:8000"
echo "   - API Docs: http://localhost:8000/docs"
echo "   - Flower Monitor: http://localhost:5555"
echo ""
echo "📊 Service Status:"
docker-compose ps

# Trap SIGTERM/SIGINT for graceful shutdown
trap "echo 'Shutting down...'; kill $CELERY_PID $FLOWER_PID $BACKEND_PID; docker-compose down" EXIT SIGTERM SIGINT

# Keep script running
wait
```

### 15.4 Health Check Endpoints

The system includes comprehensive health monitoring:

```python
# src/server/routes/health.py

@app.get("/health")
async def health_check():
    """Basic liveness check."""
    return {"status": "healthy"}

@app.get("/health/ready")
async def readiness_check():
    """Readiness check - all dependencies available."""
    health_status = {
        "database": await check_database_connection(),
        "redis": await check_redis_connection(),
        "celery": await check_celery_workers(),
        "llm_provider": await check_llm_api_key(),
        "cache_dir": check_cache_directory_writable()
    }

    all_healthy = all(health_status.values())
    status_code = 200 if all_healthy else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_healthy else "not_ready",
            "checks": health_status,
            "timestamp": datetime.now().isoformat()
        }
    )

@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    return {
        "active_jobs": get_active_job_count(),
        "completed_jobs_24h": get_completed_jobs_last_24h(),
        "cache_hit_rate": get_cache_hit_rate(),
        "avg_execution_time_seconds": get_avg_execution_time(),
        "celery_queue_length": get_celery_queue_length(),
        "total_tokens_used_24h": get_total_tokens_last_24h(),
        "error_rate_percent": get_error_rate_last_hour()
    }
```

### 15.5 Database Schema (Alembic Migrations)

```sql
-- Job tracking table
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    csv_path VARCHAR(512) NOT NULL,
    csv_hash VARCHAR(64) NOT NULL,
    target_column VARCHAR(255),
    user_question TEXT,
    mode VARCHAR(20) NOT NULL,  -- 'exploratory' or 'predictive'
    use_cache BOOLEAN DEFAULT FALSE,

    status VARCHAR(20) NOT NULL,  -- 'pending', 'running', 'completed', 'failed', 'cancelled'
    progress_percent INTEGER DEFAULT 0,
    current_phase VARCHAR(50),

    result_notebook_path VARCHAR(512),
    error_message TEXT,
    traceback TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    execution_time_seconds REAL,
    total_tokens_used INTEGER,
    llm_cost_usd NUMERIC(10, 4),

    cache_used BOOLEAN DEFAULT FALSE,
    phase1_quality_score REAL,
    phase2_quality_score REAL,

    metadata JSONB  -- Flexible storage for additional data
);

-- Indexes for performance
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);
CREATE INDEX idx_jobs_csv_hash ON jobs(csv_hash);
CREATE INDEX idx_jobs_mode ON jobs(mode);

-- Agent execution logs table
CREATE TABLE agent_logs (
    id BIGSERIAL PRIMARY KEY,
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    agent_name VARCHAR(100) NOT NULL,
    event_type VARCHAR(50) NOT NULL,  -- 'started', 'completed', 'failed', 'retried'
    phase VARCHAR(20),
    iteration INTEGER,

    input_data JSONB,
    output_data JSONB,
    error_message TEXT,

    tokens_used INTEGER,
    execution_time_seconds REAL,
    quality_score REAL,

    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_agent_logs_job_id ON agent_logs(job_id);
CREATE INDEX idx_agent_logs_timestamp ON agent_logs(timestamp DESC);

-- Job progress history table (populated by ProgressTracker)
CREATE TABLE job_progress (
    id BIGSERIAL PRIMARY KEY,
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    phase VARCHAR(50),
    progress INTEGER NOT NULL,
    message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_job_progress_job_id ON job_progress(job_id);

-- Cache metadata table (alternative to file-based cache)
CREATE TABLE cache_entries (
    csv_hash VARCHAR(64) PRIMARY KEY,
    csv_path VARCHAR(512) NOT NULL,
    csv_size_bytes BIGINT,
    row_count INTEGER,
    column_count INTEGER,

    profile_lock JSONB NOT NULL,
    profile_cells JSONB NOT NULL,
    profile_handoff JSONB NOT NULL,

    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    last_accessed_at TIMESTAMP,
    access_count INTEGER DEFAULT 0,

    agent_version VARCHAR(20),
    phase1_quality_score REAL
);

CREATE INDEX idx_cache_entries_expires_at ON cache_entries(expires_at);
```

### 15.6 Monitoring & Observability

**Structured Logging**:
```python
# src/utils/logger.py

import structlog
from datetime import datetime

logger = structlog.get_logger()

# Log events with structured data
logger.info(
    "job_started",
    job_id=job_id,
    mode="predictive",
    csv_path=csv_path,
    use_cache=True,
    timestamp=datetime.now().isoformat()
)

logger.warning(
    "cache_expired",
    csv_hash=csv_hash,
    cache_age_days=8,
    action="rerunning_phase1"
)

logger.error(
    "agent_execution_failed",
    agent_name="DataProfiler",
    iteration=3,
    error_type="ValidationError",
    error_message=str(error)
)
```

**Metrics Collection (Prometheus)**:
```python
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
jobs_started = Counter('jobs_started_total', 'Total jobs started', ['mode'])
jobs_completed = Counter('jobs_completed_total', 'Total jobs completed', ['mode', 'cache_used'])
jobs_failed = Counter('jobs_failed_total', 'Total jobs failed', ['mode', 'error_type'])

execution_time = Histogram('job_execution_seconds', 'Job execution time', ['mode'])
tokens_used = Histogram('tokens_used_per_job', 'Tokens used per job', ['agent'])

active_jobs = Gauge('active_jobs', 'Number of currently running jobs')
cache_hit_rate = Gauge('cache_hit_rate', 'Cache hit rate percentage')

# Usage
jobs_started.labels(mode='predictive').inc()
execution_time.labels(mode='exploratory').observe(45.2)
tokens_used.labels(agent='ExploratoryConclusionsAgent').observe(5200)
```

### 15.7 Future Enhancements Roadmap

See [FUTURE_ROADMAP.md](FUTURE_ROADMAP.md) for the complete roadmap.

#### Planned Enhancements

**Performance & Scalability**
- Streaming LLM responses with server-sent events for real-time agent output
- Distributed execution with horizontal scaling across multiple workers
- Enhanced token optimization and cost management

**AI & Analysis Capabilities**
- Conversational interface: "Chat with data" via natural language queries
- Multi-provider failover: Automatic LLM provider switching on failure/quota
- Active learning: System improves from user feedback/corrections
- Enhanced time series capabilities with LSTM integration

**Enterprise Features**
- ~~Authentication and authorization system~~ ✅ JWT auth + RBAC (Admin/Analyst/Viewer) + audit logging shipped
- Collaborative features: Shared analysis workspaces, commenting
- Automated PDF/HTML reports: Executive summaries with branding
- Model registry integration: MLflow/W&B for model versioning
- Model deployment: One-click API endpoint generation from notebooks
- Git integration: Auto-commit notebooks with meaningful messages
- Enterprise SSO (SAML/OIDC)
- PII detection & masking before LLM calls

