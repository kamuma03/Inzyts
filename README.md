# Inzyts - Analyze. Predict. Discover.

<div align="center">

**Autonomous Data Analysis Pipeline Powered by LangGraph & LLMs**

[![Version](https://img.shields.io/badge/version-0.10.0-blue.svg)](https://github.com/kamuma03/Inzyts/releases/tag/v0.10.0)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey.svg)](#-installation)
[![License](https://img.shields.io/badge/license-Apache_2.0-orange.svg)](LICENSE)
[![LangGraph](https://img.shields.io/badge/powered_by-LangGraph-purple.svg)](https://langchain-ai.github.io/langgraph/)
[![Status](https://img.shields.io/badge/status-Beta-yellow.svg)](https://github.com/kamuma03/Inzyts)
[![Tests](https://img.shields.io/badge/tests-108_files-brightgreen.svg)](tests/)
[![CI](https://img.shields.io/github/actions/workflow/status/kamuma03/Inzyts/test.yml?branch=main&label=CI)](.github/workflows/test.yml)

[Features](#-key-features) • [Installation](#-installation) • [Quick Start](#-quick-start) • [Documentation](#-documentation) • [Examples](#-examples)

</div>

---

## 📖 Overview

**Inzyts** is an **autonomous data analysis system** that transforms raw CSV data into comprehensive Jupyter notebooks with minimal human intervention. Built on LangGraph's stateful orchestration, it employs a **27-agent, 2-phase architecture** (Phase 1: Data Understanding → Phase 2: Analysis & Modeling) with **7-mode execution** to handle exploratory, predictive, diagnostic, comparative, forecasting, segmentation, and dimensionality reduction workflows.

### 💻 Technology Stack

<div align="center">

| Component | Technology | Description |
|-----------|------------|-------------|
| **Orchestration** | **LangGraph** | Stateful multi-agent workflow management |
| **Agent Framework** | **CrewAI** | Role-based agent delegation and tools |
| **LLMs** | **Anthropic/OpenAI/Gemini/Ollama** | Intelligent reasoning and code generation |
| **Backend** | **FastAPI** | High-performance asynchronous API |
| **Database** | **PostgreSQL** | Persistent job and profile storage |
| **Caching** | **Redis** | High-speed semantic caching |
| **Task Queue** | **Celery** | Asynchronous task processing |
| **Frontend** | **React** | Modern, responsive user interface |
| **Data Processing** | **Pandas / Scikit-learn** | Data manipulation and ML pipelines |
| **Validation** | **Pydantic** | Strict data validation and schema enforcement |
| **Cloud Storage** | **boto3 / GCS / Azure Blob** | S3, GCS, Azure cloud data ingestion |
| **Report Export** | **WeasyPrint / python-pptx / Jinja2** | PDF, PPTX, HTML, Markdown report generation |
| **Deployment** | **Docker** | Containerized, reproducible environments |

</div>

### What Makes Inzyts Unique?

- **🎯 Seven-Mode Pipeline**: Exploratory, Predictive, Diagnostic, Comparative, Forecasting, Segmentation, and Dimensionality modes
- **⚡ Smart Caching**: Phase 1 results cached for 7 days, enabling instant mode switching
- **🤖 27-Agent Orchestra**: Specialized agents for every analysis need with autonomous execution
- **🔄 Self-Correcting**: Quality validation loops with automatic retry and improvement
- **🔒 Profile Lock**: Immutable data contracts prevent hallucinations between phases
- **🧹 Data Quality Remediation**: Automated detection and fixing of data quality issues
- **📉 Dimensionality Reduction**: Dedicated PCA/t-SNE analysis mode with visual insights
- **💬 Conversational Follow-Up**: Ask follow-up questions against generated notebooks — new cells generated and executed inline
- **🎨 Modern UI**: Ink Black theme with real-time agent trace and token tracking
- **📄 Report Export**: One-click export to PDF, HTML, PowerPoint, or Markdown with executive summaries and PII detection
- **🌐 Multi-Interface**: CLI and Web UI with Docker deployment
- **🔌 LLM Agnostic**: Works with Anthropic Claude, OpenAI, Google Gemini, or local Ollama

---

## ✨ Feature Highlights

### 🔍 Advanced Analysis Capabilities
- **Seven-Mode Pipeline**: Support for Exploratory, Predictive, Diagnostic, Comparative, Forecasting, Segmentation, and Dimensionality analysis.
- **Dimensionality Reduction**: Dedicated PCA/t-SNE analysis mode with visual insights (Scree plots, 2D/3D projections).
- **Automated Data Quality Remediation**: Detects and fixes missing values, outliers, and duplicates with safety-rated remediation plans.
- **Parameter Tuning**: Automated hyperparameter optimization for ML models with GridSearchCV.

### 📂 Data Management & Integration
- **SQL Database Integration**: Connect directly to SQL databases (PostgreSQL, MySQL, etc.) to extract data using explicit queries or an autonomous SQL Agent. All generated queries are validated as read-only `SELECT` statements via AST parsing (sqlglot); results are capped at `SQL_MAX_ROWS` (default 200,000) rows and `SQL_MAX_COLS` (default 500) columns.
- **Cloud Data Warehouses**: Native support for BigQuery, Snowflake, Redshift, and Databricks via SQLAlchemy dialects — same SQL agent workflow with warehouse-specific URI schemes.
- **Cloud Storage Ingestion**: Pull data directly from **AWS S3**, **Google Cloud Storage**, and **Azure Blob Storage**. Supports CSV, JSON, Excel, and Parquet with automatic format conversion. File size limits and credential-from-environment security enforced.
- **REST API Data Extraction**: Fetch data from any REST API with configurable authentication (Bearer token, API key, Basic auth), custom headers, pagination, and JMESPath-based response extraction. SSRF protection blocks requests to private/reserved IP ranges.
- **Multi-File CSV Support**: Analyze multiple related CSV files simultaneously with intelligent join detection.
- **Domain Template System**: Define and use custom analysis templates for specific domains (finance, healthcare, etc.).
- **Data Dictionary Integration**: Import data dictionaries for enhanced column understanding and business context.
- **Smart Caching**: Phase 1 results are cached for 7 days, enabling instant mode switching and significant cost savings.
- **Exclude Columns**: Filter out PII or irrelevant columns from analysis.

### ⚡ Interactive
- **Interactive Notebooks**: Edit individual code cells with natural language ("Make this a pie chart") — powered by a lightweight CellEditAgent and persistent kernel sessions.
- **Conversational Follow-Up Analysis**: Ask follow-up questions ("Why is Cluster 2 the largest?") and get new analysis cells generated, executed, and rendered inline. Conversations persist across server restarts.
- **Inline Chart Rendering**: Base64-encoded matplotlib/seaborn charts displayed directly in the interactive cell viewer.
- **Live Notebook Panel**: Native Inzyts cell-execution UI — kernels run under a hardened ``KernelSandbox`` (resource limits, process-group SIGKILL on timeout, network egress block, secret stripping). Output streams cell-by-cell via WebSocket; same look-and-feel as the rest of the Command Center.
- **Modern UI**: "Ink Black" theme with real-time agent traces, job monitoring, and token tracking.
- **Production Architecture**: Docker-based deployment with FastAPI, PostgreSQL, Redis, and Celery.
- **Comprehensive API**: RESTful v2 API with WebSocket support for real-time updates.
- **Smart Mode Suggestion**: AI-powered analysis mode recommendation based on your question and target column — debounced API calls with confidence scoring and one-click apply.
- **Phase-Aware Progress Tracking**: Real-time progress bar with ETA, elapsed time per phase, and structured event streaming via Redis-backed ProgressTracker and Socket.IO.

### 📄 Report Export & Intelligence
- **Multi-Format Export**: Generate polished reports in **HTML**, **PDF** (via WeasyPrint), **PowerPoint** (via python-pptx), and **Markdown** from any completed analysis notebook.
- **Executive Summary Generation**: LLM-powered executive summaries with key findings, data quality highlights, and actionable recommendations — automatic fallback to notebook extraction when LLM is unavailable.
- **PII Detection & Masking**: Regex-based scanning for emails, phone numbers, SSNs, credit cards, and IP addresses with optional masking in exported reports. PII warnings displayed in the UI.
- **Branded HTML Reports**: Professional Jinja2-templated reports with Inzyts branding, embedded charts, syntax-highlighted code cells, and print-friendly CSS.
- **PowerPoint Slide Decks**: Auto-generated presentation slides with title, executive summary, per-section findings with embedded chart images, and metrics appendix.

## 🏗️ Architecture & Core System

### Architecture (27-Agent System)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Inzyts System                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  📊 Input: CSV / SQL DB / Cloud Storage / REST API + Question + Mode     │
│       ↓                                                                  │
│  🎯 Orchestrator (Mode Detection, Cache, 27-Agent Coordination)         │
│       ↓                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  PHASE 1: Data Understanding (3 Agents)                         │    │
│  │                                                                  │    │
│  │  1. Data Profiler (Hybrid LLM + Heuristics + Quality Detection) │    │
│  │  2. Profile Code Generator (+ Remediation Code)                 │    │
│  │  3. Profile Validator (Sandbox Execution)                       │    │
│  │        ↓                                                         │    │
│  │  [PROFILE LOCK] → Cache Save (7-day TTL)                        │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│       ↓                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  EXTENSIONS (3 Agents - Mode-Specific)                          │    │
│  │  • Forecasting Extension (time parsing)                         │    │
│  │  • Comparative Extension (group detection)                      │    │
│  │  • Diagnostic Extension (causal analysis)                       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│       ↓                                                                  │
│  ┌──────┬──────┬──────┬──────┬──────┬──────┬──────┐                     │
│  │EXPLOR│PREDIC│DIAGNO│COMPAR│FORECA│SEGMEN│ DIM  │                     │
│  │(1)   │(3)   │(3)   │(3)   │(3)   │(3)   │(3)   │                     │
│  ├──────┼──────┼──────┼──────┼──────┼──────┼──────┤                     │
│  │Concl.│Strat.│Root  │A/B   │Time  │Cluster│ PCA │                     │
│  │Agent │Agent │Cause │Test  │Series│Agent │Agent │                     │
│  │      │   ↓  │Agent │Agent │Agent │   ↓  │   ↓  │                     │
│  │      │Code  │   ↓  │   ↓  │   ↓  │Code  │Code  │                     │
│  │      │Gen   │Code  │Code  │Code  │Gen   │Gen   │                     │
│  │      │   ↓  │Gen   │Gen   │Gen   │   ↓  │   ↓  │                     │
│  │      │Valid.│   ↓  │   ↓  │   ↓  │Valid.│Valid.│                     │
│  │      │      │Valid.│Valid.│Valid.│      │      │                     │
│  └──────┴──────┴──────┴──────┴──────┴──────┴──────┘                     │
│       ↓                                                                  │
│  📓 Output: Executable Jupyter Notebook                                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 27-Agent System

| # | Agent | Phase | Purpose | Key Features |
|---|-------|-------|---------|--------------|
| 1 | **Orchestrator** | Control | Workflow coordination | 7-mode detection, cache mgmt, agent routing |
| 2 | **Data Profiler** | Phase 1 | Data analysis | Hybrid LLM + heuristic type detection, quality issue detection |
| 3 | **Profile Code Generator** | Phase 1 | Code generation | Creates profiling cells + remediation code |
| 4 | **Profile Validator** | Phase 1 | Quality assurance | Sandbox execution, PEP8 checks (≥0.70) |
| 5 | **Forecasting Extension** | Extension | Time series prep | Date parsing, seasonality detection |
| 6 | **Comparative Extension** | Extension | Group detection | A/B group identification, cohort analysis |
| 7 | **Diagnostic Extension** | Extension | Causal prep | Feature correlation, dependency analysis |
| 8 | **Exploratory Conclusions** | Exploratory | Insight synthesis | LLM-powered findings & recommendations |
| 9 | **Predictive Strategy** | Predictive | ML planning | Algorithm selection, feature engineering |
| 10 | **Predictive Code Generator** | Predictive | Code generation | Scikit-learn training + evaluation code |
| 11 | **Predictive Validator** | Predictive | Validation | Accuracy/R² threshold checks (≥0.60/0.50) |
| 12 | **Forecasting Strategy** | Forecasting | Time series planning | ARIMA, Prophet, seasonal decomposition |
| 13 | **Forecasting Code Generator** | Forecasting | Code generation | Time series model code, forecast plots |
| 14 | **Forecasting Validator** | Forecasting | Validation | RMSE, MAE, forecast accuracy checks |
| 15 | **Comparative Strategy** | Comparative | Statistical planning | t-tests, chi-square, effect size approach |
| 16 | **Comparative Code Generator** | Comparative | Code generation | A/B test code, confidence intervals |
| 17 | **Comparative Validator** | Comparative | Validation | Statistical significance checks |
| 18 | **Diagnostic Strategy** | Diagnostic | Causal planning | Root cause, feature importance, SHAP plan |
| 19 | **Diagnostic Code Generator** | Diagnostic | Code generation | SHAP values, causal graph code |
| 20 | **Diagnostic Validator** | Diagnostic | Validation | Causal metric and completeness checks |
| 21 | **Segmentation Strategy** | Segmentation | Clustering planning | K-means, DBSCAN, hierarchical approach |
| 22 | **Segmentation Code Generator** | Segmentation | Code generation | Clustering + silhouette evaluation code |
| 23 | **Segmentation Validator** | Segmentation | Validation | Silhouette score, cluster quality checks |
| 24 | **Dimensionality Strategy** | Dimensionality | Feature reduction planning | PCA, t-SNE, variance analysis |
| 25 | **Dimensionality Code Generator** | Dimensionality | Code generation | PCA/t-SNE code, Scree plots, 2D/3D projections |
| 26 | **SQL Extraction Agent** | Data Ingestion | Autonomous SQL extraction | Schema introspection, NL→SQL, sqlglot AST validation, read-only enforcement |
| 27 | **API Extraction Agent** | Data Ingestion | REST API data extraction | HTTP fetching, auth handling, JMESPath extraction, SSRF protection |

### Core Capabilities

- **🔄 Self-Correcting Loops**: Validators trigger retries with improvement feedback (max 3-4 iterations)
- **🔒 Immutable Handoffs**: Pydantic schemas enforce strict data contracts between agents
- **⏱️ Smart Timeouts**: 60s per cell, prevents infinite loops
- **🛡️ Sandbox Execution**: Isolated namespace, no file system access, allowlist imports only
- **📊 Quality Scoring**: Weighted metrics for code quality, execution success, and output completeness
- **🔍 Data Quality Detection**: Missing values (>50%), high cardinality (>0.95), type ambiguity
- **🧹 Data Quality Remediation**: Automated detection and fixing of quality issues with 25+ remediation strategies
- **📉 PCA Assessment**: Automatic evaluation of dimensionality reduction applicability
- **⚡ Performance Optimizations**: Lazy loading, sampling (10K rows for >100K datasets), parallel profiling

---

## 🚀 Installation

### Prerequisites

- **Docker Desktop** (recommended — includes Docker Compose)
  - [Linux](https://docs.docker.com/engine/install/) | [Windows](https://docs.docker.com/desktop/install/windows-install/) | [macOS](https://docs.docker.com/desktop/install/mac-install/)
  - Windows users: enable the **WSL 2 backend** during installation
- **Python 3.10+** (needed for the setup wizard)
- **Git**

> **Supported platforms**: Linux, macOS, and Windows (via Docker Desktop or WSL 2).

### Quick Start (Recommended)

The fastest way to get running — clone, run the start script, and the **interactive setup wizard** handles everything else:

**Linux / macOS:**

```bash
git clone https://github.com/kamuma03/Inzyts.git
cd Inzyts
./start_app.sh
```

**Windows (PowerShell):**

```powershell
git clone https://github.com/kamuma03/Inzyts.git
cd Inzyts
.\start_app.ps1
```

On first run, the setup wizard will launch and guide you through:

1. **LLM Provider** — Anthropic Claude, OpenAI, Google Gemini, or local Ollama
2. **API Key** — your provider's API key (skipped for Ollama)
3. **Model Selection** — choose from available models for your provider
4. **Admin Credentials** — username and password for the web UI
5. **Database Password** — PostgreSQL password (auto-generated if you press Enter)
6. **Security Tokens** — JWT secret and API token (all auto-generated)

The wizard writes a `.env` file and then starts all Docker services automatically.

> To reconfigure later: `python scripts/setup_wizard.py --force`

### Manual Installation (Advanced)

If you prefer to configure things manually:

#### Step 1: Clone Repository

```bash
git clone https://github.com/kamuma03/Inzyts.git
cd Inzyts
```

#### Step 2: Create Virtual Environment

```bash
# Linux / macOS
python -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

```bash
pip install -r requirements.txt
```

#### Step 3: Configure Environment Variables

```bash
cp config/.env.example .env    # Linux / macOS
Copy-Item config\.env.example .env   # Windows PowerShell
```

At minimum, set your LLM provider API key and required secrets:

```bash
# LLM provider and key
INZYTS__LLM__DEFAULT_PROVIDER=anthropic
INZYTS__LLM__ANTHROPIC_API_KEY=your_key_here

# Required secrets (generate each with: openssl rand -hex 32)
JWT_SECRET_KEY=<generate>
INZYTS_API_TOKEN=<generate>
JUPYTER_TOKEN=<generate>
POSTGRES_PASSWORD=<choose>
ADMIN_PASSWORD=<choose>
```

See [config/.env.example](config/.env.example) for all available options including OpenAI, Google Gemini, and local Ollama support.

#### Step 4: Verify Installation

```bash
python -m src.main --help
```

---

## 🎯 Quick Start

### Basic Usage

#### 1. Exploratory Analysis (Answer Questions)

```bash
# Simple question
python -m src.main --csv data/sales.csv --question "What drives revenue?"

# With explicit mode
python -m src.main \
    --csv data/customers.csv \
    --mode exploratory \
    --question "What is the customer age distribution?"
```

**Output**: Jupyter notebook with data profiling + LLM-generated insights answering your question.

#### 2. Predictive Modeling (Train ML Models)

```bash
# Target column implies predictive mode
python -m src.main --csv data/titanic.csv --target Survived

# Explicit predictive mode with custom output
python -m src.main \
    --csv data/churn.csv \
    --target Churn \
    --mode predictive \
    --output results/
```

**Output**: Jupyter notebook with profiling + trained models + evaluation metrics.

#### 3. Cache-Powered Upgrade Flow

```bash
# Day 1: Run exploratory analysis
python -m src.main --csv data/sales.csv --question "What correlates with sales?"
# → Creates cache at ~/.Inzyts_cache/<hash>/

# Day 2: Upgrade to predictive (instant, uses cache)
python -m src.main --csv data/sales.csv --target sales --use-cache
# → Skips Phase 1, jumps to ML modeling
```

### Advanced Usage

#### With Data Dictionary

```bash
python -m src.main \
    --csv data/medical_records.csv \
    --target disease \
    --data-dictionary data/columns_definition.csv
```

Data dictionary format (CSV):
```csv
column_name,description
age,"Patient age in years"
bmi,"Body Mass Index"
disease,"0=healthy, 1=diagnosed"
```

#### Force Fresh Analysis (Ignore Cache)

```bash
python -m src.main --csv data.csv --target price --no-cache
```

#### Clear Expired Caches

```bash
python -m src.main --clear-cache
```

#### Verbose Logging

```bash
python -m src.main --csv data.csv --target y --verbose
```

---

## 🌐 Web Interface

### Quick Start with Docker Compose

The recommended way to run the full stack (backend + frontend + database):

```bash
# Linux / macOS
./start_app.sh

# Windows (PowerShell)
.\start_app.ps1
```

The start script automatically runs the **setup wizard** on first launch to create your `.env` file. If you already have a `.env`, it starts Docker directly.

You can also start services manually:

```bash
docker compose up -d --build
```

This starts:
- **PostgreSQL** (127.0.0.1:5432) - Database (localhost-only, not exposed externally)
- **Redis** (127.0.0.1:6379) - Cache & message broker (localhost-only, not exposed externally)
- **FastAPI Backend** (port 8000) - REST API (runs as non-root `inzyts` user, with healthcheck)
- **React Frontend** (port 5173) - Web UI (waits for backend health before starting)
- **Celery Worker** - Background job processing (runs as non-root `inzyts` user). Hosts in-process kernel sandboxes for the Live Notebook panel — see ``src/services/sandbox_executor.py`` and the threat model in ``docs/architecture.md``.
- **Flower** (port 5555) - Celery monitoring (optional)

All services have memory limits enforced via Docker resource constraints, and are connected through isolated Docker networks (`backend` and `db`).

Access the interfaces:
- **Web UI**: http://localhost:5173
- **API Docs**: http://localhost:8000/docs
- **Flower Monitor**: http://localhost:5555

### Manual Backend Startup (Development)

```bash
# Ensure PostgreSQL and Redis are running
docker compose up -d db redis

# Run database migrations
alembic upgrade head

# Start Celery worker (separate terminal)
celery -A src.server.celery_app worker --loglevel=info          # Linux / macOS
celery -A src.server.celery_app worker --loglevel=info --pool=solo  # Windows

# Start FastAPI server
uvicorn src.server.main:app --reload --port 8000
```

> **Windows note**: Celery's default `prefork` pool is not supported on Windows. Use `--pool=solo` (single-threaded) or `--pool=threads`. This is handled automatically when running via Docker.

### Manual Frontend Startup (Development)

```bash
cd frontend
npm install
npm run dev
# Access at http://localhost:5173
```

### Features

- **📁 File Upload**: Drag-and-drop CSV upload with robust delimiter auto-detection
- **🔍 File Preview**: Preview uploaded file contents (first 5 rows) before analysis
- **⚡ Cache Detection**: Automatic cache status checking with visual indicators
- **🎯 Smart Mode Selection**: AI-powered mode suggestion with confidence scoring, detailed descriptions, and one-click apply
- **📊 Phase-Aware Progress**: Real-time progress with ETA, elapsed time per phase, and structured agent event streaming
- **🔄 Job Management**: Cancel running jobs, view execution logs, download results
- **📓 Live Notebook Panel**: Run cells against a hardened in-process kernel sandbox; output streams via WebSocket; Inzyts dark-theme rendering (no Jupyter Lab iframe).
- **🚀 One-Click Upgrade**: Convert exploratory to predictive with cached profile

### API Endpoints

**v2 API (Current)**

All endpoints require a `Authorization: Bearer <token>` header. Rate limits are enforced per client IP:
- `POST /api/v2/analyze` — 10 requests/minute
- `POST /api/v2/auth/login` — 10 requests/minute (per source IP)
- `GET /api/v2/jobs/{job_id}` — 30 requests/minute

**Auth column legend**: `Public` = no auth, `Any` = any authenticated user (viewer/analyst/admin), `Owner` = the user who created the job (admins bypass), `Analyst+` = analyst or admin role required, `Admin` = admin role required.

| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/api/v2/auth/login` | POST | Authenticate and obtain JWT token | Public |
| `/api/v2/auth/me` | GET | Get current user profile (id, username, role) | Any |
| `/api/v2/analyze` | POST | Start new analysis job | Analyst+ |
| `/api/v2/suggest-mode` | POST | AI-powered analysis mode suggestion | Any |
| `/api/v2/jobs` | GET | List jobs (admins see all; non-admins see their own) | Any |
| `/api/v2/jobs/{job_id}` | GET | Get job status, progress, and logs | Owner |
| `/api/v2/jobs/{job_id}/cancel` | POST | Cancel running job | Owner |
| `/api/v2/jobs/{job_id}/columns` | GET | Per-column profile rows (Command Center) | Owner |
| `/api/v2/jobs/{job_id}/cost` | GET | Per-phase cost breakdown | Owner |
| `/api/v2/notebooks/{job_id}/download` | GET | Download completed notebook (.ipynb) | Owner |
| `/api/v2/notebooks/{job_id}/html` | GET | Get rendered HTML notebook | Owner |
| `/api/v2/notebooks/{job_id}/cells` | GET | Get notebook as structured JSON cells | Owner |
| `/api/v2/notebooks/{job_id}/cells/edit` | POST | Edit cell with natural language instruction | Owner |
| `/api/v2/notebooks/{job_id}/cells/execute` | POST | Execute cell in live kernel session | Owner |
| `/api/v2/notebooks/{job_id}/cells/restart` | POST | Restart kernel session for the job | Owner |
| `/api/v2/notebooks/{job_id}/cells/interrupt` | POST | Interrupt the currently-running cell | Owner |
| `/api/v2/notebooks/{job_id}/ask` | POST | Ask follow-up question against notebook | Owner |
| `/api/v2/notebooks/{job_id}/conversation` | GET | Load conversation history | Owner |
| `/api/v2/files/upload` | POST | Upload CSV/Parquet/Excel/JSON file | Analyst+ |
| `/api/v2/files/upload_batch` | POST | Upload multiple files | Analyst+ |
| `/api/v2/files/preview` | GET | Preview file content (first 5 rows) | Any |
| `/api/v2/files/db-test` | POST | Test database connection (lists tables) | Any |
| `/api/v2/files/sql-preview` | POST | Preview a SELECT query result | Any |
| `/api/v2/files/api-preview` | POST | Preview a REST API response | Any |
| `/api/v2/templates` | GET | List all domain templates | Any |
| `/api/v2/templates` | POST | Upload new domain template | Any |
| `/api/v2/templates/{domain}` | DELETE | Delete domain template | Any |
| `/api/v2/metrics` | GET | System health metrics | Any |
| `/api/v2/reports/{job_id}/export` | GET, POST | Export report (html / pdf / pptx / markdown) | Owner |
| `/api/v2/reports/{job_id}/executive-summary` | GET | Get LLM-generated executive summary | Owner |
| `/api/v2/reports/{job_id}/pii-scan` | GET | Scan notebook for PII findings | Owner |
| `/api/v2/admin/users` | GET | List all users | Admin |
| `/api/v2/admin/users` | POST | Create new user with role | Admin |
| `/api/v2/admin/users/{user_id}` | PUT | Update user (role, email, active, password) | Admin |
| `/api/v2/admin/users/{user_id}` | DELETE | Delete user | Admin |
| `/api/v2/admin/audit-logs` | GET | Query audit logs (filter by user, action, date) | Admin |
| `/api/v2/admin/audit-logs/summary` | GET | Audit log action counts | Admin |
| `/health` | GET | Liveness check | Public |

**WebSocket Events** (Socket.IO on `/socket.io`)
- `job_started`, `job_progress`, `job_completed`, `job_failed`, `agent_event`, `progress` (phase-aware with ETA)

**Live Notebook WebSocket Events**
- Kernel messages relayed bidirectionally between client and Jupyter Server
- Supports `execute_request`, `execute_reply`, `stream`, `error` message types

### Example API Usage

```bash
# Check cache status
curl -X POST http://localhost:8000/api/v2/cache/check \
  -H "Content-Type: application/json" \
  -d '{"csv_path": "/path/to/data.csv"}'

# Start analysis
curl -X POST http://localhost:8000/api/v2/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "csv_path": "/path/to/data.csv",
    "target": "price",
    "mode": "predictive",
    "use_cache": true
  }'
# Returns: {"job_id": "uuid-here", "status": "pending", "estimated_time": 120}

# Check status (poll every 2-5 seconds)
curl http://localhost:8000/api/v2/jobs/<job_id>
# Returns: {"job_id": "...", "status": "running", "progress": 45, "current_phase": "Phase2"}

# Download result when complete
curl -O http://localhost:8000/api/v2/notebooks/<job_id>

# View system metrics
curl http://localhost:8000/api/v2/metrics
```

---

## 📚 Documentation

### Mode Detection Logic

The system determines pipeline mode using this priority:

1. **Explicit `--mode` flag** (highest priority)
   ```bash
   --mode exploratory     # Forces exploratory
   --mode predictive      # Forces predictive
   --mode diagnostic      # Forces diagnostic
   --mode comparative     # Forces comparative
   --mode forecasting     # Forces forecasting
   --mode segmentation    # Forces segmentation
   --mode dimensionality  # Forces dimensionality
   ```

2. **Target column presence** (implies predictive)
   ```bash
   --target Survived  # Automatically sets predictive mode
   ```

3. **Keyword inference from question** (7-mode detection)
   - **Exploratory**: distribution, correlation, summary, statistics, describe, explore
   - **Predictive**: predict, model, classify, train, regression
   - **Diagnostic**: why, root cause, diagnose, investigate, explain why
   - **Comparative**: compare, A/B test, difference, versus, control vs
   - **Forecasting**: forecast, predict future, time series, next quarter, trend
   - **Segmentation**: segment, cluster, group, persona, cohort
   - **Dimensionality**: dimensionality, PCA, principal component, reduce dimensions, t-SNE
   ```bash
   --question "Predict customer churn"              # → predictive
   --question "What is the age distribution?"        # → exploratory
   --question "Why did sales drop?"                  # → diagnostic
   --question "Compare control vs variant"           # → comparative
   --question "Forecast next quarter sales"          # → forecasting
   --question "Segment customers into groups"        # → segmentation
   --question "Reduce dimensionality of features"    # → dimensionality
   ```

4. **Default**: EXPLORATORY mode (if no clear signals)

### Smart Mode Suggestion API

The frontend provides real-time mode suggestions as users type their analysis question:

1. **User types a question** in the analysis form (e.g., "forecast next month sales")
2. **Debounced API call** (500ms) to `POST /api/v2/suggest-mode`
3. **Backend ModeDetector** analyzes question keywords and target column
4. **Response** includes `suggested_mode`, `confidence` (high/medium/low), and `explanation`
5. **UI shows suggestion** badge on recommended mode card with "Apply" button

```bash
# Example
curl -X POST /api/v2/suggest-mode \
  -H "Authorization: Bearer <token>" \
  -d '{"question": "forecast next month sales"}'

# Response
{
  "suggested_mode": "forecasting",
  "detection_method": "inferred_keyword",
  "confidence": "medium",
  "explanation": "Question keywords suggest forecasting analysis."
}
```

### Cache System Details

**Location**: `~/.Inzyts_cache/`

**Structure**:
```
~/.Inzyts_cache/
├── <sha256_csv_hash>/
│   ├── metadata.json               # Cache creation time, TTL, version
│   ├── profile_lock.json           # Immutable Phase 1 outputs
│   ├── profile_cells.json          # Notebook cells from profiling
│   ├── profile_handoff.json        # ProfileToStrategyHandoff data
│   └── exploratory_conclusions_<q_hash>/  # Per-question insights
└── cache_index.json                # Quick lookup: path → hash
```

**Cache Statuses**:
- `NOT_FOUND`: No cache exists for this CSV
- `VALID`: Cache exists, CSV unchanged, not expired (<7 days)
- `EXPIRED`: Cache exists but >7 days old (auto-deleted)
- `CSV_CHANGED`: CSV file modified since cache creation (hash mismatch)

**Cache Behavior**:
- **Exploratory → Exploratory**: Reuses cached profile, generates new insights if question changed
- **Exploratory → Predictive**: Reuses cached profile, skips Phase 1 entirely
- **Predictive → Predictive**: If target changes, requires fresh Phase 1

### Configuration Reference

Edit `src/config.py` for advanced customization:

```python
class Phase1Config:
    max_profile_codegen_recursions = 3  # Max retry attempts
    quality_threshold = 0.70            # Minimum acceptable quality
    timeout_seconds = 120               # Max execution time

class Phase2Config:
    max_analysis_codegen_recursions = 4
    quality_threshold = 0.70
    min_model_accuracy = 0.60           # Classification threshold
    min_r2_score = 0.50                 # Regression threshold

class CacheConfig:
    ttl_days = 7                        # Cache expiration
    auto_save = True                    # Save after Phase 1
    hash_algorithm = "sha256"           # Integrity checking

class ExploratoryConclusionsConfig:
    min_findings = 3                    # Minimum key findings
    min_recommendations = 2             # Minimum recommendations
    min_confidence = 0.70               # Quality threshold
    max_retries = 3                     # LLM generation retries
```

---

## 📊 Output Examples

### Exploratory Mode Notebook Structure

All notebooks use consistent numbered headings (# 1., ## 2., ## 3., ## 4.) for clear section hierarchy.

```
┌─────────────────────────────────────────┐
│ # 1. Title & Introduction               │
│    Question: "What factors affect sales?"│
├─────────────────────────────────────────┤
│ ## 2. Setup & Data Loading              │
│    2.1 Imports                          │
│    import pandas, numpy, matplotlib...  │
│    2.2 Data Loading                     │
│    df = pd.read_csv('sales.csv')        │
│    df.shape: (10000, 15)                │
├─────────────────────────────────────────┤
│ ## 3. Data Profiling & Quality          │
│    3.1 Data Overview                    │
│    • Column type detection              │
│    • Statistics (mean, std, quartiles)  │
│    3.2 Data Quality Report              │
│    • Missing value report               │
│    • Quality score: 0.87                │
├─────────────────────────────────────────┤
│ ## 4. Exploratory Analysis Conclusions  │
│    Direct Answer:                       │
│       "Sales are primarily driven by    │
│        customer_age (r=0.68) and        │
│        marketing_spend (r=0.54)..."     │
│                                         │
│    Key Findings:                        │
│       - Ages 25-40 account for 60% ...  │
│       - Seasonal peaks in Q4...         │
│       - High churn in segment B...      │
│                                         │
│    Statistical Insights:                │
│       - Strong positive correlation...  │
│       - Outliers detected in price...   │
│                                         │
│    Recommendations:                     │
│       - Focus marketing on age 25-40... │
│       - Investigate segment B issues... │
│                                         │
│    Limitations:                         │
│       - Missing values in 12% of data.. │
│                                         │
│    Confidence: 0.85                     │
└─────────────────────────────────────────┘
```

### Predictive Mode Notebook Structure

```
┌─────────────────────────────────────────┐
│ # 1. Title & Introduction               │
│    Target: Churn (Binary Classification)│
├─────────────────────────────────────────┤
│ ## 2. Setup & Data Loading              │
│    (Same structure as exploratory)      │
├─────────────────────────────────────────┤
│ ## 3. Data Profiling & Quality          │
│    (Same structure as exploratory)      │
├─────────────────────────────────────────┤
│ ## 4. Analysis                          │
│    4.1 Data Preprocessing               │
│    • Train/test split (80/20)           │
│    • Feature scaling (StandardScaler)   │
│    • Encoding (LabelEncoder/OneHot)     │
│    • Handling missing values            │
│                                         │
│    4.2 Model Training                   │
│    Models trained:                      │
│    • Logistic Regression                │
│    • Random Forest                      │
│    • XGBoost                            │
│                                         │
│    4.3 Model Evaluation                 │
│    Model Performance:                   │
│    • Logistic: 0.78 accuracy            │
│    • RandomForest: 0.84 accuracy        │
│    • XGBoost: 0.82 accuracy             │
│    Detailed: Precision, Recall, F1, AUC │
│                                         │
│    4.4 Results Visualization            │
│    • Confusion matrices                 │
│    • ROC curves                         │
│    • Feature importance (top 10)        │
│                                         │
│    4.5 Analysis Conclusions             │
│     Best Model: Random Forest (0.84)    │
│     Key Features: tenure, age, usage... │
│     Recommendations: Deploy model...    │
└─────────────────────────────────────────┘
```

---

## 💡 Examples

### Example 1: Customer Churn Analysis

**Scenario**: Understand what drives customer churn, then build a predictive model.

```bash
# Step 1: Exploratory analysis
python -m src.main \
    --csv data/customers.csv \
    --question "What factors correlate with customer churn?" \
    --mode exploratory

# Output: churn_exploratory_analysis_20260105_143022.ipynb
# Contains: Profiling + LLM insights about churn factors

# Step 2: Build predictive model (uses cached profile)
python -m src.main \
    --csv data/customers.csv \
    --target Churn \
    --use-cache

# Output: churn_predictive_model_20260105_150145.ipynb
# Contains: Cached profiling + Trained models + Evaluation
```

### Example 2: Real Estate Price Prediction

```bash
python -m src.main \
    --csv data/housing.csv \
    --target price \
    --mode predictive \
    --data-dictionary data/housing_dict.csv

# Automatically:
# 1. Profiles data (detects numeric/categorical features)
# 2. Identifies regression task (continuous target)
# 3. Trains LinearRegression, RandomForest, GradientBoosting
# 4. Evaluates with MAE, RMSE, R² metrics
# 5. Generates feature importance plots
```

### Example 3: Healthcare Data Exploration

```bash
python -m src.main \
    --csv data/medical_records.csv \
    --question "What are the main health risk factors in this population?" \
    --verbose

# Generates comprehensive report with:
# - Age/gender distribution analysis
# - BMI patterns and outliers
# - Correlation between risk factors
# - LLM-synthesized medical insights
# - Data quality warnings (if any)
```

### Example 4: Time Series Forecasting

```bash
python -m src.main \
    --csv data/sales_time_series.csv \
    --question "Forecast next quarter sales" \
    --mode forecasting

# Automatically:
# 1. Detects date/time columns via Forecasting Extension
# 2. Parses temporal patterns (seasonality, trends)
# 3. Applies time series models (ARIMA, Prophet)
# 4. Generates future predictions with confidence intervals
# 5. Visualizes forecast vs historical data
```

### Example 5: A/B Test Analysis

```bash
python -m src.main \
    --csv data/ab_test_results.csv \
    --question "Compare control vs variant performance" \
    --mode comparative

# Automatically:
# 1. Identifies control/variant groups via Comparative Extension
# 2. Calculates statistical significance (t-test, chi-square)
# 3. Computes effect sizes and confidence intervals
# 4. Generates comparison visualizations
# 5. Provides recommendations on test results
```

### Example 6: Customer Segmentation

```bash
python -m src.main \
    --csv data/customer_data.csv \
    --question "Segment customers into groups" \
    --mode segmentation

# Automatically:
# 1. Identifies relevant features for clustering
# 2. Determines optimal number of segments
# 3. Applies clustering algorithms (K-means, DBSCAN)
# 4. Creates segment profiles and personas
# 5. Visualizes segments with PCA/t-SNE
```

### Example 7: Root Cause Analysis

```bash
python -m src.main \
    --csv data/incident_logs.csv \
    --question "Why did system failures increase last month?" \
    --mode diagnostic

# Automatically:
# 1. Analyzes correlations via Diagnostic Extension
# 2. Identifies causal relationships
# 3. Computes feature importance and SHAP values
# 4. Traces root causes of anomalies
# 5. Provides actionable diagnostic insights
```

### Example 8: Dimensionality Reduction

```bash
python -m src.main \
    --csv data/high_dimensional_features.csv \
    --question "Reduce dimensionality and visualize clusters" \
    --mode dimensionality

# Automatically:
# 1. Assesses PCA applicability (feature count > 20)
# 2. Performs PCA with optimal component selection
# 3. Generates Scree plot for variance explained
# 4. Creates 2D and 3D projections
# 5. Produces component loadings heatmap
# 6. Interprets top principal components
```

### Example 9: Data Quality Remediation

```bash
python -m src.main \
    --csv data/messy_data.csv \
    --target outcome \
    --mode predictive

# Automatically:
# 1. Detects quality issues (missing values, outliers, duplicates)
# 2. Generates remediation plans with safety ratings
# 3. Creates dual-path analysis (original vs. remediated)
# 4. Applies safe remediations automatically
# 5. Flags risky remediations for user review
```

### Example 10: SQL Database Integration

**Scenario**: Extract and analyze data directly from a SQL database either explicitly or using natural language.

```bash
# Explicit Ingestion Bridge
# Provide the exact query to execute and extract data
python -m src.main \
    --db-uri "postgresql://user:pass@localhost:5432/mydb" \
    --db-query "SELECT date, sum(amount) as revenue FROM sales GROUP BY date" \
    --question "Forecast revenue for the next quarter" \
    --mode forecasting

# Autonomous SQL Agent
# The agent introspects the schema and writes the query to answer your question
python -m src.main \
    --db-uri "postgresql://user:pass@localhost:5432/mydb" \
    --question "Analyze the monthly revenue trends for the last year"
```

---

## 🛠️ Troubleshooting

### Common Issues

#### Issue 1: ModuleNotFoundError

**Error**:
```
ModuleNotFoundError: No module named 'langgraph'
```

**Solution**:
```bash
pip install -r requirements.txt --upgrade
```

#### Issue 2: API Key Not Found

**Error**:
```
Error: ANTHROPIC_API_KEY not found in environment
```

**Solution**:
1. Create `.env` file in root directory
2. Add: `ANTHROPIC_API_KEY=your_key_here`
3. Or export: `export ANTHROPIC_API_KEY=your_key_here`

#### Issue 3: Cache Permission Denied

**Error**:
```
PermissionError: [Errno 13] Permission denied: '~/.Inzyts_cache/'
```

**Solution**:
```bash
# Create cache directory manually
mkdir -p ~/.Inzyts_cache
chmod 755 ~/.Inzyts_cache

# Or specify custom cache location in .env
echo "CACHE_DIR=/tmp/inzyts_cache" >> .env
```

#### Issue 4: Notebook Validation Failed

**Error**:
```
Validation Failed: Quality score 0.55 below threshold 0.70
```

**Solution**:
- Check CSV data quality (missing values, encoding issues)
- Try with `--verbose` flag to see detailed errors
- Simplify your question or target column
- Lower quality threshold in `src/config.py` (not recommended)

#### Issue 5: LLM Timeout

**Error**:
```
TimeoutError: LLM request timed out after 60 seconds
```

**Solution**:
```python
# In src/config.py, increase timeout:
class LLMConfig:
    request_timeout = 120  # Increase from 60 to 120 seconds
```

#### Issue 6: Memory Error on Large CSV

**Error**:
```
MemoryError: Unable to allocate array
```

**Solution**:
- System automatically samples large files (>100K rows)
- For very large files, pre-sample manually:
```bash
# Sample first 50,000 rows
head -n 50000 large_data.csv > sampled_data.csv
python -m src.main --csv sampled_data.csv --target y
```

### Debug Mode

Enable detailed logging:

```bash
# Console logging
python -m src.main --csv data.csv --target y --verbose

# Log to file
python -m src.main --csv data.csv --target y --verbose 2> debug.log
```

### Getting Help

- **Issues**: [GitHub Issues](https://github.com/kamuma03/Inzyts/issues)
- **Discussions**: [GitHub Discussions](https://github.com/kamuma03/Inzyts/discussions)
- **Documentation**: [architecture.md](architecture.md), [FUTURE_ROADMAP.md](FUTURE_ROADMAP.md)

---

## 🔒 Security

### Hardening Notes

| Area | Behaviour |
|------|-----------|
| **Authentication** | JWT-based login with bcrypt password hashing. Bearer tokens verified with `secrets.compare_digest()` (constant-time). Tokens stored in `sessionStorage` only — never `localStorage` or compiled into the Vite bundle. `ADMIN_PASSWORD` is required (no default) — the server refuses to start without it. |
| **RBAC** | Three-tier role hierarchy: **Admin > Analyst > Viewer**. Roles stored in the `users` table and embedded in JWT claims. `require_role()` FastAPI dependency enforces role checks with hierarchy awareness (admins pass analyst-level checks). Admin-only endpoints: user management (`/admin/users`) and audit log queries (`/admin/audit-logs`). Frontend routes protected with role-based guards. |
| **Audit logging** | All security-relevant actions (login, failed login, analysis start, file upload, user CRUD) are recorded in the `audit_logs` table with timestamp, user, action, IP address, HTTP method/path, and status code. `AuditMiddleware` auto-logs API requests; `record_audit()` provides fine-grained logging from route handlers. Audit log failures never break the request flow. |
| **File paths** | Upload paths validated with `Path.resolve()` + `is_relative_to()`. Symlinks are explicitly rejected on both original and resolved paths to prevent TOCTOU escape from the allowed directory. Upload directory has restricted permissions (`chmod 750`). |
| **SQL queries** | All LLM-generated SQL is parsed with `sqlglot` AST validation. Only plain `SELECT` statements are permitted; any DML (`INSERT`, `UPDATE`, `DELETE`, `DROP`, etc.) — including CTE-embedded DML — is blocked. SQLite URIs are rejected. Results are capped at `SQL_MAX_ROWS` rows and `SQL_MAX_COLS` columns. Database connections enforce read-only transactions (`SET TRANSACTION READ ONLY`). |
| **Rate limiting** | `POST /analyze` is limited to 10 req/min; `GET /jobs/{id}` to 30 req/min (via `slowapi`). |
| **Docker** | Backend and Celery worker containers run as non-root user `inzyts`. `POSTGRES_PASSWORD` has no default — compose fails loudly if the variable is unset. Database and Redis ports bound to `127.0.0.1` (not exposed externally). Services are isolated across `backend` and `db` networks with memory limits enforced. Backend includes a healthcheck; frontend waits for backend health before starting. |
| **Sandbox execution** | Validator agents execute generated code in an isolated namespace with a safe-imports allowlist (no network, no file-write, no subprocess). Output truncated to prevent memory exhaustion. |
| **Credential masking** | Log messages are automatically scrubbed of database URI credentials (`user:pass@`) and API keys/tokens before emission to WebSocket clients. |
| **Kernel bootstrap** | Dataset paths are passed to Jupyter kernels via environment variables (not string interpolation) to prevent code injection. Kernel sessions use LRU eviction when the session limit is reached. |
| **Frontend XSS** | All markdown rendered via `dangerouslySetInnerHTML` is sanitized with DOMPurify using a strict tag/attribute allowlist. |
| **Error responses** | API error messages never expose internal details (stack traces, file paths). Errors are logged server-side and generic messages are returned to clients. |
| **Credentials** | Never set `VITE_API_TOKEN` in `docker-compose.yml` — Vite bakes `VITE_*` vars into the compiled JS bundle. Enter the API token at runtime in the browser UI. |

---

## 🧪 Testing

### Test Suite Overview

The system includes **108 Python test files** (~1,100 assertions) plus **9 frontend `vitest` files**, exercised in CI on every push to `main` via [`.github/workflows/test.yml`](.github/workflows/test.yml). Coverage is not currently measured automatically — run `./tests/run_tests.sh --html` locally to generate a coverage report.

```bash
# Run the default unit suite (fast, no external deps).
# `slow`-marked tests are excluded by default — see warning below.
JWT_SECRET_KEY=test-secret ADMIN_PASSWORD=test-admin pytest tests/unit

# Run integration tests (requires Redis; conftest auto-starts a container).
JWT_SECRET_KEY=test-secret ADMIN_PASSWORD=test-admin pytest tests/integration

# Run frontend tests
(cd frontend && npm run test)

# Helper script (legacy — invokes pytest with the same defaults)
./tests/run_tests.sh
```

> **⚠️ The `slow` marker — read before running.** The single test file
> `tests/unit/services/test_sandbox_security.py` spawns *real* Jupyter
> kernels to exercise the `setrlimit` / `setsid` / `killpg` machinery in
> [src/services/sandbox_executor.py](src/services/sandbox_executor.py).
> A bug in any of those primitives can SIGKILL the parent process group —
> which on a desktop session may include the test runner, the shell, the
> terminal, **and the desktop session itself**. The `_killpg` helper now
> enforces three invariants that prevent this, but as defence-in-depth the
> `slow` marker is **excluded by default**. Opt in explicitly with
> `pytest -m slow` only after reviewing the safety guarantees in
> [SECURITY.md](SECURITY.md#sandbox-_killpg-safety-invariants).

### Test Layout

| Layer | Test files | What it covers |
|---|---|---|
| **Unit** (`tests/unit/`) | ~70 files | Agent `process()` methods, validators, state machine, prompt builders, route handlers (with mocked DB), `_killpg` invariants, kernel env isolation, db_uri host blocklist, SQL DML guard |
| **Integration** (`tests/integration/`) | 21 files | End-to-end pipeline runs, API endpoints with TestClient + real Redis container, mode-specific workflows. **Includes**: SSRF redirect/pagination guard (`test_ssrf_redirects.py`), login rate limit (`test_login_rate_limit.py`), cross-user IDOR (`test_idor_cross_user.py`), role-based access (`test_role_based_access.py`) |
| **Security** (`tests/security/`) | 2 files | Adversarial inputs: path traversal, JWT tampering, malicious uploads, sandbox-escape primitives (rlimit / setsid / proxy / credential-stripping invariants) |
| **Safety** (`tests/safety/`) | 1 file | Prompt injection in SQL agent, credential-name echo prevention in LLM prompts, mode-detector adversarial input |
| **Contracts** (`tests/contracts/`) | 1 file | OpenAPI fuzz via `schemathesis` — every documented GET endpoint must never 5xx under conforming inputs |
| **Agents** (`tests/agents/`) | 4 files | API/SQL extraction agents, profile multi-file merging, parameter tuning codegen |
| **Services** (`tests/services/`) | 2 files | Join detector, template manager |
| **Performance** (`tests/performance/`) | 1 file | Throughput benchmarks |
| **End-to-end** (`tests/e2e/`) | 1 file | Multi-file workflow |
| **UI** (`tests/ui/`) | 1 file | Smoke test |
| **Frontend Vitest** (`frontend/src/**/*.test.{ts,tsx}`) | 9 files | Component + utility unit tests |
| **Playwright e2e + a11y** (`frontend/tests/`) | 2 files | Login → Dashboard critical journey, WCAG-AA scan via `@axe-core/playwright`. Run with `npx playwright test` after `./start_app.sh`. |

### Test Fixtures

```bash
tests/fixtures/
├── iris.csv                    # Clean, small classification dataset
├── Bank_Churn.csv              # Real-world churn with missing values
├── synthetic_large.csv         # Performance testing (100K+ rows)
├── titanic.csv                 # Binary classification benchmark
└── housing.csv                 # Regression benchmark
```

### Running Specific Test Suites

```bash
# Unit tests only (fast, no external dependencies)
pytest tests/unit/ -v

# Integration tests (requires database)
docker-compose up -d postgres redis
pytest tests/integration/ -v

# Web API tests (requires full stack)
./start_app.sh &
pytest tests/test_web_integration.py -v

# Performance tests (slow, benchmarking)
pytest tests/test_performance.py -v --benchmark

# Test with different LLM providers
ANTHROPIC_API_KEY=xxx pytest tests/ -v
OPENAI_API_KEY=xxx pytest tests/ -v
```

### Test Development

```bash
# Run tests in watch mode (auto-rerun on file changes)
pytest-watch tests/

# Run with debugger on failure
pytest tests/ --pdb

# Generate test report
pytest tests/ --html=report.html --self-contained-html
```

---



> **Future Plans**: See [FUTURE_ROADMAP.md](docs/FUTURE_ROADMAP.md) for planned features including SSO, scheduled analysis, and advanced analytics. Enterprise security (RBAC + audit logging), report export (HTML/PDF/PPTX/Markdown), executive summaries, and PII detection are now shipped.

---

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **LangGraph** - Stateful orchestration framework
- **CrewAI** - Agent framework and LLM integration
- **Pydantic** - Data validation and schema enforcement
- **Anthropic Claude** - Recommended LLM provider
- **scikit-learn** - ML algorithms and preprocessing

---

## 📞 Support

- **Documentation**: [architecture.md](architecture.md) - Deep technical details
- **Roadmap**: [FUTURE_ROADMAP.md](FUTURE_ROADMAP.md) - Planned features
- **Issues**: [GitHub Issues](https://github.com/kamuma03/Inzyts/issues)

---

<div align="center">

**Made with ❤️ by the Inzyts Team**

📊 **Production Stats**:
- 27-agent, 2-phase architecture with 7 pipeline modes
- 108 backend test files (~1,100 assertions) + 9 frontend Vitest files; CI on every push to main
- Smart mode suggestion with AI-powered confidence scoring
- Phase-aware progress tracking with real-time ETA
- Multi-format report export (HTML, PDF, PPTX, Markdown) with executive summaries and PII detection
- Dimensionality Reduction Mode with PCA/t-SNE
- Data Quality Remediation with 25+ safety-rated strategies
- Multi-file CSV support with intelligent join detection
- Live Notebook Execution with Jupyter Server integration
- Interactive Notebooks with cell-level natural language editing
- Comprehensive documentation (README, architecture, testing guides)
- Multi-LLM support (Anthropic, OpenAI, Google, Ollama)
- Full-stack deployment (FastAPI + React + PostgreSQL + Redis + Celery + Jupyter)
- Modern UI with real-time agent trace and token tracking

[⬆ Back to Top](#inzyts---analyze-predict-discover)

</div>
