# Inzyts Test Suite

**Status**: ✅ Complete | **Coverage**: 95%+ | **Test Files**: 96 | **Last Updated**: 2026-03-21

---

## Quick Start

```bash
# Run all tests
./tests/run_tests.sh

# Run specific suite
./tests/run_tests.sh -s unit          # Unit tests
./tests/run_tests.sh -s integration   # Integration tests
./tests/run_tests.sh -s workflow      # Workflow tests
./tests/run_tests.sh -s db            # Real database tests (requires Docker)

# Generate HTML coverage report
./tests/run_tests.sh --html

# Run UI tests (requires app running)
./start_app.sh                        # In terminal 1
./tests/run_ui_tests.sh               # In terminal 2
```

---

## Table of Contents

1. [Overview](#overview)
2. [Test Structure](#test-structure)
3. [Running Tests](#running-tests)
4. [Coverage Statistics](#coverage-statistics)
5. [Test Files Reference](#test-files-reference)
6. [Writing Tests](#writing-tests)
7. [Troubleshooting](#troubleshooting)

---

## Overview

The Inzyts test suite provides comprehensive coverage of the multi-agent data analysis system with 27 agents orchestrated via LangGraph across 2 phases and 7 pipeline modes, plus data ingestion agents for SQL, cloud storage, and REST API sources.

### Key Statistics

| Metric | Value |
|--------|-------|
| **Overall Coverage** | 95%+ |
| **Total Test Files** | 96 |
| **Total Test Functions** | ~1125+ |
| **Total Test Lines** | ~21,000 |
| **Unit Test Coverage** | 92%+ |
| **Integration Coverage** | 85%+ |
| **Server/API Coverage** | 80%+ |

### Coverage Improvement Journey

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Overall Coverage** | 65% | 95%+ | +30% |
| **Unit Tests** | 70% | 92%+ | +22% |
| **Integration Tests** | 60% | 85%+ | +25% |
| **Server/API** | 20% | 80%+ | +60% |
| **Test Files** | 18 | 96 | +78 new files |
| **Test Lines** | ~3,500 | ~21,000+ | +17,500+ lines |

---

## Test Structure

```
tests/
├── README.md                    # This file
├── conftest.py                  # Root conftest — auto-starts Redis Docker container
├── run_tests.sh                 # Main test runner
├── run_ui_tests.sh              # UI test runner
│
├── unit/                        # Unit Tests (66 files)
│   ├── agents/                  # Agent Tests
│   │   ├── test_base_agent.py              # Base agent, LLM providers (474 lines)
│   │   ├── phase1/
│   │   │   ├── test_data_profiler.py       # Data profiling
│   │   │   ├── test_profile_codegen.py     # Profile code generation (797 lines)
│   │   │   ├── test_profile_validator.py   # Profile validation
│   │   │   └── test_exploratory_conclusions.py
│   │   ├── phase2/
│   │   │   ├── test_strategy.py            # Strategy agent
│   │   │   ├── test_analysis_codegen.py    # Analysis code generation
│   │   │   ├── test_analysis_codegen_methods.py  # Mode-specific methods (600 lines)
│   │   │   ├── test_analysis_validator_full.py   # Full validation (450 lines)
│   │   │   └── test_orchestrator.py        # Phase 2 orchestrator
│   │   └── extensions/
│   │       └── test_extensions.py          # Extension agents
│   │
│   ├── models/                  # Model Tests
│   │   ├── test_state.py                   # AnalysisState, Issue, AgentOutput (621 lines)
│   │   ├── test_profile_lock.py            # ProfileLock mechanism (726 lines)
│   │   ├── test_handoffs.py                # All handoff models (1,006 lines)
│   │   ├── test_cells.py                   # NotebookCell, CellManifest (691 lines)
│   │   ├── test_validation_modes.py        # Validation mode logic
│   │   └── test_codegen_templates.py       # Code generation templates
│   │
│   ├── services/                # Service Tests
│   │   ├── test_pii_detector.py            # PII detection & masking (237 lines)
│   │   ├── test_executive_summary.py       # Executive summary generation (228 lines)
│   │   ├── test_report_exporter.py         # Multi-format report export (319 lines)
│   │   ├── test_cost_estimator.py          # Cost estimation logic
│   │   ├── test_jupyter_proxy.py           # Jupyter proxy service
│   │   ├── test_kernel_session_manager.py  # Kernel session lifecycle
│   │   ├── test_metrics_service.py         # Metrics collection
│   │   ├── test_notebook_assembler.py      # Notebook assembly
│   │   ├── test_progress_tracker.py        # Progress tracking service
│   │   ├── test_sandbox_executor.py        # Sandbox code execution
│   │   └── test_template_manager_ops.py    # Template management operations
│   │
│   ├── server/routes/           # Server Route Tests
│   │   ├── test_analysis.py               # Analysis endpoint tests
│   │   ├── test_auth_route.py             # Auth route tests
│   │   ├── test_files.py                  # File upload/preview routes
│   │   ├── test_jobs.py                   # Job management routes
│   │   ├── test_metrics.py                # Metrics endpoint tests
│   │   ├── test_notebooks.py              # Notebook routes
│   │   ├── test_reports.py                # Report export API endpoints (239 lines)
│   │   └── test_websockets.py             # WebSocket route tests
│   │
│   ├── server/middleware/       # Middleware Tests
│   │   ├── test_audit.py                  # Audit logging middleware
│   │   ├── test_auth.py                   # Auth middleware
│   │   └── test_rbac.py                   # Role-based access control
│   │
│   ├── workflow/                # Workflow Tests
│   │   ├── test_graph_workflow.py          # Graph orchestration (972 lines) ⭐
│   │   ├── test_routing.py                 # Phase routing, rollback (550 lines)
│   │   └── test_graph_routing.py           # Data source routing (SQL, API, cache) (6 tests)
│   │
│   ├── test_config.py             # CloudConfig, APISourceConfig (4 tests)
│   │
│   ├── test_llm_integration.py  # LLM integration tests
│   ├── test_error_handling.py   # Error handling
│   ├── test_logger.py           # Logging utilities
│   ├── test_extensions.py       # Extension system
│   ├── test_strategies.py       # Strategy helpers
│   └── test_validation_modes.py # Validation modes
│
├── integration/                 # Integration Tests (16 files)
│   ├── conftest.py                         # Testcontainers Postgres fixture (session-scoped)
│   ├── test_api_files.py                   # File upload/preview endpoints (300 lines)
│   ├── test_api_jobs.py                    # Job management endpoints (350 lines)
│   ├── test_api_analysis.py                # Analysis endpoints (400 lines)
│   ├── test_sql_real_db.py                 # Real DB integration (23 tests, testcontainers) 🐘
│   ├── test_e2e_workflow.py                # End-to-end workflow
│   ├── test_cache_manager.py               # Cache integration
│   ├── test_integration.py                 # General integration
│   ├── test_mode_inference.py              # Mode inference logic
│   ├── test_core_modes_workflow.py         # Core pipeline modes workflow
│   └── test_web_integration.py             # Web API integration
│
├── performance/                 # Performance Tests (1 file)
│   └── test_perf_workload.py               # Performance benchmarks
│
├── ui/                          # UI Tests (1 file)
│   ├── conftest.py                         # Playwright configuration
│   └── test_ui_smoke.py                    # UI smoke tests
│
├── agents/                      # Agent-Level Tests (2 files)
│   ├── test_sql_agent.py                  # SQL extraction agent (12 tests)
│   └── test_api_agent.py                  # API extraction agent (17 tests)
│
├── server/services/             # Server Service Tests
│   ├── test_cloud_ingestion.py            # Cloud storage ingestion (18 tests)
│   └── test_data_ingestion.py             # SQL/file data ingestion tests
│
└── fixtures/                    # Test Fixtures
    ├── sample_data/             # Sample CSV files
    └── expected_notebooks/      # Expected notebook outputs
```

---

## Running Tests

### Using Test Runner Scripts

#### Main Test Runner (`./tests/run_tests.sh`)

```bash
# Show help
./tests/run_tests.sh --help

# Run all tests
./tests/run_tests.sh

# Run specific suite
./tests/run_tests.sh -s unit          # Unit tests only
./tests/run_tests.sh -s integration   # Integration tests only
./tests/run_tests.sh -s performance   # Performance tests only
./tests/run_tests.sh -s ui            # UI tests only

# Run by component
./tests/run_tests.sh -s workflow      # Workflow tests
./tests/run_tests.sh -s models        # Model tests
./tests/run_tests.sh -s agents        # Agent tests

# Run by priority
./tests/run_tests.sh -s priority1     # Priority 1 (core infrastructure)
./tests/run_tests.sh -s priority2     # Priority 2 (server/API layer)

# Generate HTML coverage report
./tests/run_tests.sh --html

# Custom coverage threshold
./tests/run_tests.sh --threshold 90

# Verbose output
./tests/run_tests.sh -v

# Quick mode (skip slow tests)
./tests/run_tests.sh --quick
```

#### UI Test Runner (`./tests/run_ui_tests.sh`)

```bash
# Start application first
./start_app.sh

# In another terminal, run UI tests
./tests/run_ui_tests.sh
```

### Using pytest Directly

```bash
# All tests with coverage
pytest tests/ --cov=src --cov-report=html -v

# Unit tests only
pytest tests/unit/ --cov=src --cov-report=term -v

# Integration tests only
pytest tests/integration/ --cov=src --cov-report=term -v

# Real database tests (requires Docker)
pytest tests/integration/test_sql_real_db.py -v -m requires_db

# Specific test file
pytest tests/unit/workflow/test_graph_workflow.py -v

# Specific test class
pytest tests/unit/workflow/test_graph_workflow.py::TestInitializeNode -v

# Specific test function
pytest tests/unit/workflow/test_graph_workflow.py::TestInitializeNode::test_initialize_node_success -v

# With coverage threshold
pytest tests/ --cov=src --cov-fail-under=95

# Generate HTML coverage report
pytest tests/ --cov=src --cov-report=html
# Open: htmlcov/index.html
```

---

## Coverage Statistics

### Overall Coverage by Component

| Component | Coverage | Status |
|-----------|----------|--------|
| **Core Agents** | 90%+ | ✅ Excellent |
| **Models** | 95%+ | ✅ Excellent |
| **Workflow** | 90%+ | ✅ Excellent |
| **Server/API** | 80%+ | ✅ Good |
| **Utilities** | 85%+ | ✅ Good |
| **Overall** | 95%+ | ✅ Excellent |

### Test Distribution

| Category | Files | Lines | Coverage |
|----------|-------|-------|----------|
| **Unit Tests** | 66 | ~18,000+ | 92%+ |
| **Integration Tests** | 16 | ~3,700+ | 85%+ |
| **Agent Tests** | 2 | ~400+ | 90%+ |
| **Server Service Tests** | 2 | ~300+ | 85%+ |
| **Performance Tests** | 1 | ~200 | N/A |
| **UI Tests** | 1 | ~200 | N/A |
| **Total** | **96** | **~21,200+** | **95%+** |

---

## Test Files Reference

### Priority 1: Core Infrastructure (10 files)

#### Agent Tests
1. **`test_base_agent.py`** (474 lines)
   - Base agent initialization
   - LLM provider handling (OpenAI, Anthropic, Gemini, Ollama)
   - CrewAI agent configuration
   - Issue creation and tracking

2. **`test_profile_codegen.py`** (797 lines)
   - Profile code generation with LLM
   - Template fallback mechanism
   - Cache hit/miss scenarios
   - Column type-specific generation

3. **`test_analysis_codegen_methods.py`** (600 lines)
   - Diagnostic template generation
   - Comparative template generation
   - Forecasting template generation
   - Segmentation template generation

4. **`test_analysis_validator_full.py`** (450 lines)
   - Full validation process
   - Cell validation logic
   - Mode-specific metric detection
   - PEP8 scoring
   - Validation report building

#### Model Tests
5. **`test_state.py`** (621 lines)
   - AnalysisState model
   - Issue tracking
   - Phase enum validation
   - State transitions

6. **`test_profile_lock.py`** (726 lines)
   - ProfileLock mechanism
   - Lock granting/denial logic
   - Integrity checks and verification
   - Hash calculation stability

7. **`test_handoffs.py`** (1,006 lines)
   - All handoff model validations
   - Serialization/deserialization roundtrips
   - Field constraints
   - Enum validations

8. **`test_cells.py`** (691 lines)
   - NotebookCell creation
   - nbformat conversion
   - CellManifest dependency tracking
   - Edge cases (unicode, special chars)

#### Workflow Tests
9. **`test_routing.py`** (550 lines)
   - Phase 1/2 recursion routing
   - Rollback detection
   - Oscillation detection
   - Issue frequency tracking

10. **`test_graph_workflow.py`** (972 lines) ⭐ **Most Comprehensive**
    - All 14 workflow nodes tested
    - 3 conditional routing functions
    - Token tracking across nodes
    - Error propagation
    - State transitions
    - All 6 pipeline modes
    - 60+ test cases

    **Test Classes**:
    - `TestInitializeNode` - Workflow initialization
    - `TestRestoreCacheNode` - Cache restoration
    - `TestPhase1Nodes` - Phase 1 agent nodes
    - `TestExtensionNode` - Extension agent execution
    - `TestPhase2Nodes` - Phase 2 agent nodes
    - `TestAssemblyNode` - Notebook assembly
    - `TestExploratoryConclusionsNode` - Exploratory mode
    - `TestRollbackRecoveryNode` - Rollback mechanism
    - `TestConditionalRouting` - Routing logic
    - `TestBuildWorkflow` - Graph construction
    - `TestTokenTracking` - Token accumulation
    - `TestErrorPropagation` - Error handling
    - `TestStateTransitions` - Phase transitions

### Priority 2: Server/API Layer (7 files)

11. **`test_api_files.py`** (300 lines)
    - File upload endpoint
    - CSV preview endpoint
    - File validation

12. **`test_api_jobs.py`** (350 lines)
    - Job listing
    - Status retrieval
    - Job cancellation

13. **`test_api_analysis.py`** (400 lines)
    - Analysis endpoint
    - Cost estimation
    - Request validation

14. **`test_cost_estimator.py`** (300 lines)
    - CSV token estimation
    - Cost calculation per mode

15. **`test_engine.py`** (400 lines)
    - Celery task execution
    - Token tracking
    - Error handling

16. **`test_db_models.py`** (300 lines)
    - Job model CRUD
    - Status transitions

17. **`test_database.py`** (250 lines)
    - Connection management
    - Session handling

### Validated Feature Tests (Maintained)

- `test_data_profiler.py` - Data profiling logic
- `test_profile_validator.py` - Profile validation
- `test_exploratory_conclusions.py` - Exploratory mode conclusions
- `test_strategy.py` - Strategy agent
- `test_analysis_codegen.py` - Analysis code generation
- `test_orchestrator.py` - Phase 2 orchestrator
- `test_extensions.py` - Extension agents
- `test_codegen_templates.py` - Code templates
- `test_validation_modes.py` - Validation modes
- `test_llm_integration.py` - LLM integration
- `test_error_handling.py` - Error handling
- `test_logger.py` - Logging
- `test_e2e_workflow.py` - End-to-end workflow
- `test_cache_manager.py` - Cache management
- `test_integration.py` - General integration
- `test_mode_inference.py` - Mode inference
- `test_core_modes_workflow.py` - Core modes workflow
- `test_web_integration.py` - Web API
- `test_perf_workload.py` - Performance
- `test_ui_smoke.py` - UI smoke tests
- `test_multifile_workflow.py` - Multi-file workflow
- `test_quality_and_dimensionality.py` - Advanced features (PCA, remediation)

### Data Source Tests (March 2026)

18. **`test_sql_real_db.py`** (200+ lines) — **Real Database Integration** 🐘
    - Uses `testcontainers[postgres]` to spin up a throwaway PostgreSQL 15 container
    - **TestIngestFromSQL** (7 tests): basic extraction, filtered/aggregation queries, empty results, row-limit truncation, connection errors, invalid queries
    - **TestReadOnlyEnforcement** (5 tests): verifies `SET TRANSACTION READ ONLY` blocks INSERT, UPDATE, DELETE, DROP on real Postgres
    - **TestValidationRoundTrip** (9 tests): `_validate_select_only` + real execution for valid queries; rejection of dangerous queries
    - **TestConnectionCleanup** (2 tests): 20 sequential ingests with no connection leak; recovery after failed query
    - **Prerequisites**: Docker daemon running; `pip install testcontainers[postgres]`

19. **`test_sql_agent.py`** (172 lines)
    - SQL extraction agent validation
    - Missing DB URI / question handling
    - sqlite rejection, stacked statements, CTE-embedded DML
    - `_validate_select_only` unit tests
    - Successful query execution with chunked read

20. **`test_api_agent.py`** (242 lines)
    - Auth header building (Bearer, API key, Basic)
    - SSRF protection (`_is_private_ip`)
    - JMESPath data extraction
    - API agent process: success, timeout, HTTP error, empty response
    - Bearer auth header verification

21. **`test_cloud_ingestion.py`** (188 lines)
    - Cloud URI scheme validation (s3, gs, az, abfs, abfss; rejects http, ftp, file)
    - Format conversion (CSV passthrough, JSON→CSV, Excel→CSV)
    - S3 download (boto3 mock via sys.modules), size limit enforcement
    - GCS download (google.cloud.storage mock)
    - Azure download (missing connection string error)
    - `ingest_from_cloud` dispatch for all providers

22. **`test_graph_routing.py`** (6 tests)
    - `route_after_initialize` for SQL extraction, API extraction
    - SQL precedence over API when both present
    - Cache restore, data merger, default phase1 routing

23. **`test_config.py`** (4 tests)
    - `CloudConfig` defaults and custom values
    - `APISourceConfig` defaults and custom values

### Report Export & Intelligence Tests (New — March 2026)

24. **`test_pii_detector.py`** (237 lines)
    - PII detection for emails, phone numbers, SSNs, credit cards, IP addresses
    - False positive filtering (common IPs like 127.0.0.1)
    - Notebook scanning with deduplication
    - PII masking with partial value display
    - 30 tests across 4 test classes

25. **`test_executive_summary.py`** (228 lines)
    - Fallback summary generation from notebook content
    - LLM-powered summary with mocked provider
    - Timeout handling via ThreadPoolExecutor
    - Notebook content extraction and prompt truncation
    - JSON parsing and error recovery
    - 12 tests

26. **`test_report_exporter.py`** (319 lines)
    - HTML export with Jinja2 template rendering
    - Markdown export with notebook cell conversion
    - PDF/PPTX dependency error handling
    - Section parsing, metrics extraction
    - PII masking integration during export
    - 15 tests across 6 test classes

27. **`test_reports.py`** (239 lines)
    - GET/POST report export API endpoints
    - Executive summary endpoint
    - PII scan endpoint with real detection
    - Job not found / no notebook error cases
    - Format validation
    - 10 tests across 4 test classes

---

## Writing Tests

### Test Naming Convention

```python
def test_<component>_<scenario>_<expected_outcome>():
    """Test that <component> <does something> when <scenario>."""
    # Arrange - Set up test data and mocks

    # Act - Execute the code under test

    # Assert - Verify the results
```

### Test Structure (AAA Pattern)

```python
import pytest
from unittest.mock import Mock, patch, MagicMock

class TestComponentName:
    """Tests for ComponentName class."""

    @pytest.fixture
    def mock_dependency(self):
        """Fixture for mocked dependency."""
        return Mock()

    def test_happy_path(self, mock_dependency):
        """Test normal execution path."""
        # Arrange
        component = ComponentName(mock_dependency)

        # Act
        result = component.method()

        # Assert
        assert result == expected_value

    def test_error_case(self, mock_dependency):
        """Test error handling."""
        # Arrange
        mock_dependency.side_effect = Exception("Error")
        component = ComponentName(mock_dependency)

        # Act & Assert
        with pytest.raises(Exception):
            component.method()

    def test_edge_case(self, mock_dependency):
        """Test edge case with empty input."""
        # Arrange
        component = ComponentName(mock_dependency)

        # Act
        result = component.method(None)

        # Assert
        assert result is None
```

### Mocking Strategy

**Do Mock:**
- External dependencies (LLM API calls, filesystem)
- Network requests
- Time-dependent operations
- Random operations

**Don't Mock (use testcontainers instead):**
- Database read-only enforcement — mocks can't verify `SET TRANSACTION READ ONLY` actually blocks writes
- Row-limit truncation — mocks bypass the real `pd.read_sql(..., chunksize=N)` path
- Connection pool cleanup — mocks can't detect leaked connections
- See `tests/integration/test_sql_real_db.py` for examples

**Don't Mock:**
- Internal logic being tested
- Simple data structures
- Pure functions
- Internal method calls

**Example:**
```python
@patch('src.agents.base.LLMAgent')
@patch('src.agents.base.get_llm')
@patch('src.agents.base.CrewAgent')
def test_agent_initialization(self, mock_crew, mock_get_llm, mock_llm_agent):
    """Test agent initialization with mocked LLM."""
    # Mock external LLM
    mock_get_llm.return_value = Mock()

    # Test internal logic
    agent = MyAgent(...)

    # Assert internal state (not mocked)
    assert agent.name == "expected_name"
```

### Test Quality Checklist

- [ ] **Structure**
  - [ ] Clear test class organization
  - [ ] Descriptive test names
  - [ ] Proper fixtures for reusable data
  - [ ] AAA (Arrange-Act-Assert) pattern

- [ ] **Coverage**
  - [ ] Happy path (normal execution)
  - [ ] Error paths (exceptions, validation failures)
  - [ ] Edge cases (empty data, nulls, boundaries)
  - [ ] Integration points (handoffs, state transitions)

- [ ] **Mocking**
  - [ ] External dependencies mocked
  - [ ] Internal logic not mocked
  - [ ] Realistic test data
  - [ ] Proper patch levels

- [ ] **Performance**
  - [ ] Fast execution (<1s per test)
  - [ ] No flaky tests
  - [ ] Isolated tests
  - [ ] No interdependencies

---

## Troubleshooting

### Tests Not Found

```bash
# Make sure you're in the project root
cd /path/to/Inzyts

# Check test files exist
ls -la tests/unit/

# Verify Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Import Errors

```bash
# Install dependencies
pip install -r requirements.txt

# Install test dependencies
pip install pytest pytest-cov pytest-mock

# Check Python version (requires 3.10+)
python --version
```

### Coverage Too Low

```bash
# Check which files lack coverage
pytest tests/ --cov=src --cov-report=term-missing

# Generate detailed HTML report
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html

# Run specific component tests
pytest tests/unit/workflow/ --cov=src/workflow -v
```

### UI Tests Failing

```bash
# Make sure app is running
./start_app.sh

# Check frontend
curl http://localhost:5173

# Check backend
curl http://localhost:8000/health

# Install playwright browsers
python -m playwright install chromium

# Run with headed mode for debugging
pytest tests/ui --headed --slowmo 1000
```

### Database Integration Tests Failing

```bash
# Ensure Docker daemon is running
docker info

# Install testcontainers
pip install testcontainers[postgres]

# Run database tests only
pytest tests/integration/test_sql_real_db.py -v -m requires_db

# If Docker socket permission denied
sudo usermod -aG docker $USER  # then re-login
```

### Slow Test Execution

```bash
# Run in parallel (install pytest-xdist)
pip install pytest-xdist
pytest tests/ -n auto

# Skip slow tests
pytest tests/ -m "not slow"

# Run only fast tests
pytest tests/unit/ --quick
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-mock

      - name: Run tests
        run: |
          pytest tests/ --cov=src --cov-fail-under=95 --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

### Pre-commit Hook Example

```bash
# .git/hooks/pre-commit
#!/bin/bash
set -e

echo "Running tests before commit..."
./tests/run_tests.sh -s unit --quick

echo "Tests passed! Proceeding with commit."
```

---

## Test Suite Quality Standards

All tests in this suite adhere to:

✅ **pytest Conventions**
- Standard pytest naming and structure
- Proper fixture usage
- Clear test organization

✅ **AAA Pattern**
- Arrange: Set up test data and mocks
- Act: Execute the code under test
- Assert: Verify the results

✅ **Comprehensive Coverage**
- Happy path scenarios
- Error handling paths
- Edge cases
- Integration points

✅ **Proper Mocking**
- External dependencies mocked (LLM, DB, filesystem, cache)
- Internal logic tested without mocks
- Realistic test data
- Appropriate patch levels

✅ **Performance**
- Fast execution (<1s per test)
- No flaky tests
- Isolated tests
- No interdependencies

---

## Additional Resources

### Documentation
- **Main README**: [../README.md](../README.md) - Project overview
- **Requirements**: [../requirements.md](../requirements.md) - System requirements

### Test Execution Scripts
- **Main Test Runner**: [run_tests.sh](run_tests.sh) - Comprehensive test runner
- **UI Test Runner**: [run_ui_tests.sh](run_ui_tests.sh) - UI-specific tests

### Coverage Reports
After running tests with `--html`:
- **HTML Report**: `htmlcov/index.html` - Interactive coverage visualization
- **Terminal Report**: Displayed automatically after test run

---

## Maintenance

### Adding New Tests

1. **Choose appropriate location**:
   - `unit/` for isolated component tests
   - `integration/` for multi-component tests
   - `performance/` for benchmark tests
   - `ui/` for Playwright tests

2. **Follow naming convention**:
   - File: `test_<component>.py`
   - Class: `TestComponentName`
   - Function: `test_<scenario>_<outcome>`

3. **Run tests**:
   ```bash
   pytest tests/unit/test_new_component.py -v
   ```

4. **Check coverage**:
   ```bash
   pytest tests/unit/test_new_component.py --cov=src/new_component
   ```

### Updating Tests

When source code changes:
1. Update relevant test files
2. Run affected tests
3. Verify coverage maintains 95%+
4. Update fixtures if needed

---

## Summary

The Inzyts test suite provides **95%+ coverage** with **96 test files** and **~1125+ test functions**, ensuring:

- ✅ Reliable system behavior
- ✅ Comprehensive error handling
- ✅ Integration point validation
- ✅ Performance benchmarking
- ✅ UI functionality verification

**Last Achievement**: Comprehensive 24-task architectural refactoring — extracted shared modules (validation_utils, path_validator), decomposed frontend components, added Redis Docker auto-start for tests, and updated all test mocks and assertions (March 2026).

---

**Questions or Issues?**
- Check the troubleshooting section above
- Review existing test files for examples
- Run `./tests/run_tests.sh --help` for options

**Happy Testing! 🧪**
