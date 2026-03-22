# Contributing to Inzyts

Thank you for your interest in contributing to Inzyts! This document provides guidelines to help you get started.

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ (for frontend)
- Docker and Docker Compose (for full-stack development)
- Git

### Development Setup (Linux / macOS)

1. **Fork and clone the repository**

   ```bash
   git clone https://github.com/<your-username>/Inzyts.git
   cd Inzyts
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Set up environment variables**

   ```bash
   cp config/.env.example .env
   # Edit .env with your API keys and configuration
   ```

4. **Start infrastructure services**

   ```bash
   docker-compose up -d db redis
   alembic upgrade head
   ```

5. **Run the backend**

   ```bash
   uvicorn src.server.main:app --reload --port 8000
   ```

6. **Run the frontend** (in a separate terminal)

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

### Development Setup (Windows)

> **Recommended**: Use Docker Desktop for Windows. All services (backend, worker, frontend, DB, Redis, Jupyter) run inside Linux containers, so no platform-specific changes are needed.

1. **Prerequisites**

   - Install [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/) and enable WSL 2 backend
   - Install [Git for Windows](https://git-scm.com/download/win)
   - Install [Python 3.10+](https://www.python.org/downloads/windows/) (add to PATH)
   - Install [Node.js 18+](https://nodejs.org/) (for local frontend development)

2. **Fork and clone the repository**

   ```powershell
   git clone https://github.com/<your-username>/Inzyts.git
   cd Inzyts
   ```

3. **Set up environment variables**

   ```powershell
   Copy-Item config\.env.example .env
   # Edit .env with your API keys and configuration
   ```

4. **Start the full stack via Docker**

   ```powershell
   .\start_app.ps1
   ```

   This builds and starts all services. Access:
   - Backend: http://localhost:8000
   - Frontend: http://localhost:5173
   - Jupyter: http://localhost:8888

5. **Local development (optional, without Docker)**

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt

   # Redis is required — install via:
   #   - Docker: docker run -d -p 6379:6379 redis:7.2-alpine
   #   - Or Memurai (Windows-native Redis alternative): https://www.memurai.com/

   # Start backend
   uvicorn src.server.main:app --reload --port 8000

   # Start Celery worker (must use solo pool on Windows)
   celery -A src.server.celery_app worker --loglevel=info --pool=solo

   # Start frontend (in separate terminal)
   cd frontend
   npm install
   npm run dev
   ```

### Running Tests

**Linux / macOS:**

```bash
# Run all tests
./tests/run_tests.sh

# Run specific test suites
pytest tests/unit/ -v
pytest tests/integration/ -v

# Generate coverage report
./tests/run_tests.sh --html
```

**Windows (PowerShell):**

```powershell
# Run all tests
.\tests\run_tests.ps1

# Run specific test suites
.\tests\run_tests.ps1 -Suite unit
.\tests\run_tests.ps1 -Suite integration -Verbose

# Generate coverage report
.\tests\run_tests.ps1 -Html
```

## How to Contribute

### Reporting Bugs

- Use [GitHub Issues](https://github.com/kamuma03/Inzyts/issues) to report bugs
- Include steps to reproduce, expected behavior, and actual behavior
- Include your Python version, OS, and relevant configuration

### Suggesting Features

- Open a [GitHub Issue](https://github.com/kamuma03/Inzyts/issues) with the "enhancement" label
- Describe the use case and expected behavior

### Submitting Changes

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes following the project conventions (see below)

3. Write or update tests for your changes

4. Ensure all tests pass:
   ```bash
   pytest tests/ -v
   ```

5. Commit with a clear message:
   ```bash
   git commit -m "feat: add support for new analysis mode"
   ```

6. Push and open a Pull Request against `main`

## Code Style

- **Python**: Follow PEP 8. Use type hints for function signatures.
- **TypeScript/React**: Follow existing patterns in the `frontend/` directory.
- **Commits**: Use [Conventional Commits](https://www.conventionalcommits.org/) format:
  - `feat:` for new features
  - `fix:` for bug fixes
  - `refactor:` for code restructuring
  - `docs:` for documentation changes
  - `test:` for test additions/modifications

## Project Structure

```
src/
  agents/          # 27-agent system (profiling, strategy, codegen, validation, data ingestion)
  config/          # Configuration classes and domain templates
  core/            # Core utilities
  llm/             # LLM provider integration
  models/          # Pydantic data models and handoff contracts
  server/          # FastAPI backend (routes, services, middleware, cloud ingestion)
  services/        # Core services (data loading, caching, notebooks)
  utils/           # Utility functions
  workflow/        # LangGraph workflow orchestration

frontend/src/
  components/      # React components (incl. analysis-form/ sub-components)
  constants/       # Shared constants (status styles, etc.)
  context/         # React context providers
  hooks/           # Custom React hooks (useFetchData, etc.)
  pages/           # Page-level components
  layouts/         # Layout components
  types/           # TypeScript type definitions
  utils/           # Utility functions (formatters, etc.)

tests/
  unit/            # Unit tests
  integration/     # Integration tests
  e2e/             # End-to-end tests
  server/          # API endpoint tests
  services/        # Service layer tests (data ingestion, cloud ingestion)
  agents/          # Agent-level tests (SQL agent, API agent)
  fixtures/        # Test data files
```

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
