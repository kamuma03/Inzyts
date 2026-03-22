#!/bin/bash
# Comprehensive Test Runner for Inzyts
# Created: 2026-01-13
# Purpose: Run all tests with coverage reporting and quality checks

set -e

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../scripts/common.sh"

# Default values
TEST_SUITE="all"
COVERAGE_THRESHOLD=95
VERBOSE=""
HTML_REPORT=false
UI_FLAGS=""
HEADED_MODE=false

# Help function
show_help() {
    cat << EOF
${BOLD}Inzyts Test Runner${NC}

${BOLD}Usage:${NC}
  ./run_tests.sh [options]

${BOLD}Options:${NC}
  -h, --help              Show this help message
  -s, --suite SUITE       Test suite to run: all, unit, integration, performance, ui
  -t, --threshold NUM     Coverage threshold percentage (default: 95)
  -v, --verbose           Verbose output
  --html                  Generate HTML coverage report
  --quick                 Quick test (skip slow tests)
  --headed                Run UI tests in headed mode (for debugging)

${BOLD}Examples:${NC}
  ./run_tests.sh                           # Run all tests
  ./run_tests.sh -s unit                   # Run only unit tests
  ./run_tests.sh -s integration -v         # Run integration tests with verbose output
  ./run_tests.sh --html --threshold 85     # Generate HTML report with 85% threshold
  ./run_tests.sh --quick                   # Quick test run

${BOLD}Test Suites:${NC}
  all           - All tests (unit + integration + performance)
  unit          - Unit tests only (tests/unit/)
  integration   - Integration tests only (tests/integration/)
  db            - Real database tests (testcontainers, requires Docker)
  performance   - Performance tests only (tests/performance/)
  ui            - UI smoke tests (tests/ui/)
  priority1     - Priority 1 tests (core infrastructure)
  priority2     - Priority 2 tests (server/API layer)
  workflow      - Workflow tests (graph orchestration)
  models        - Model tests (state, handoffs, cells)
  agents        - Agent tests (base, phase1, phase2)
  services      - Service tests (jupyter_proxy, etc.)
  notebooks     - Notebook API tests
  notebook-execution - Live notebook execution tests
  multi-file    - Multi-file tests (previously v180)
  templates     - Template management tests
  e2e           - End-to-end workflow tests
  advanced-features - Advanced features (dimensionality, remediation)
EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -s|--suite)
            TEST_SUITE="$2"
            shift 2
            ;;
        -t|--threshold)
            COVERAGE_THRESHOLD="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE="-vv"
            shift
            ;;
        --html)
            HTML_REPORT=true
            shift
            ;;
        --quick)
            QUICK="-m 'not slow'"
            shift
            ;;
        --headed)
            HEADED_MODE=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

echo -e "${BOLD}${BLUE}🧪 Inzyts Test Suite${NC}"
echo "=================================="
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${YELLOW}⚠️  pytest not found. Installing...${NC}"
    pip install pytest pytest-cov pytest-mock
fi

# Build pytest command based on suite
PYTEST_CMD="pytest"
COVERAGE_FLAGS="--cov=src --cov-report=term-missing"

if [ "$HTML_REPORT" = true ]; then
    COVERAGE_FLAGS="$COVERAGE_FLAGS --cov-report=html"
fi

case $TEST_SUITE in
    all)
        echo -e "${BLUE}📋 Running: All Tests${NC}"
        TEST_PATH="tests/"
        ;;
    unit)
        echo -e "${BLUE}📋 Running: Unit Tests${NC}"
        TEST_PATH="tests/unit/"
        ;;
    integration)
        echo -e "${BLUE}📋 Running: Integration Tests${NC}"
        TEST_PATH="tests/integration/"
        ;;
    db)
        echo -e "${BLUE}📋 Running: Real Database Tests (testcontainers)${NC}"

        # Check Docker is available
        if ! command -v docker &> /dev/null || ! docker info &> /dev/null; then
            echo -e "${RED}❌ Docker is required for database tests but is not running.${NC}"
            echo -e "${YELLOW}   Start Docker and try again.${NC}"
            exit 1
        fi

        # Check testcontainers is installed
        if ! python -c "import testcontainers" 2>/dev/null; then
            echo -e "${YELLOW}⚠️  testcontainers not found. Installing...${NC}"
            pip install "testcontainers[postgres]"
        fi

        TEST_PATH="tests/integration/test_sql_real_db.py"
        PYTEST_CMD="pytest -m requires_db"
        COVERAGE_FLAGS="--cov=src/server/services/data_ingestion --cov=src/agents/sql_agent --cov-report=term-missing"
        ;;
    performance)
        echo -e "${BLUE}📋 Running: Performance Tests${NC}"
        TEST_PATH="tests/performance/"
        ;;
    ui)
        echo -e "${BLUE}📋 Running: UI Tests (Playwright)${NC}"

        # Detect Python command
        if command -v python3 &> /dev/null; then
            PYTHON_CMD="python3"
        elif command -v python &> /dev/null; then
            PYTHON_CMD="python"
        else
            echo -e "${RED}❌ Python not found${NC}"
            exit 1
        fi

        # Detect pip
        PIP_CMD="pip"
        if [[ -n "$VIRTUAL_ENV" ]]; then
            echo -e "${GREEN}✓ Using virtual environment: $VIRTUAL_ENV${NC}"
            PIP_CMD="$VIRTUAL_ENV/bin/pip"
        elif [[ -d ".venv" ]]; then
            echo -e "${YELLOW}ℹ️  Found .venv but not activated. Using .venv/bin${NC}"
            PIP_CMD="./.venv/bin/pip"
        fi

        # Install Playwright dependencies
        echo -e "${BLUE}📦 Installing Playwright dependencies...${NC}"
        $PIP_CMD install pytest-playwright --quiet
        $PYTHON_CMD -m playwright install chromium

        # Check if services are running
        echo -e "${BLUE}🔍 Checking if application is running...${NC}"
        FRONTEND_RUNNING=false
        BACKEND_RUNNING=false

        if curl -s http://localhost:5173 > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Frontend running at http://localhost:5173${NC}"
            FRONTEND_RUNNING=true
        else
            echo -e "${RED}✗ Frontend not running at http://localhost:5173${NC}"
        fi

        if curl -s http://localhost:8000/health > /dev/null 2>&1 || curl -s http://localhost:8000 > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Backend running at http://localhost:8000${NC}"
            BACKEND_RUNNING=true
        else
            echo -e "${YELLOW}⚠️  Backend not running at http://localhost:8000${NC}"
        fi

        if [ "$FRONTEND_RUNNING" = false ]; then
            echo -e "${RED}❌ Frontend is not running. Start the app first: ./start_app.sh${NC}"
            exit 1
        fi

        if [ "$BACKEND_RUNNING" = false ]; then
            echo -e "${YELLOW}⚠️  Warning: Backend not running. UI tests may fail.${NC}"
        fi

        TEST_PATH="tests/ui/"
        # UI tests use different flags
        UI_FLAGS="--base-url http://localhost:5173 --slowmo 500"
        if [ "$HEADED_MODE" = true ]; then
            UI_FLAGS="$UI_FLAGS --headed"
        fi
        COVERAGE_FLAGS=""  # No coverage for UI tests
        ;;
    priority1)
        echo -e "${BLUE}📋 Running: Priority 1 Tests (Core Infrastructure)${NC}"
        TEST_PATH="tests/unit/agents/test_base_agent.py \
                   tests/unit/agents/phase1/test_profile_codegen.py \
                   tests/unit/agents/phase2/test_analysis_codegen_methods.py \
                   tests/unit/agents/phase2/test_analysis_validator_full.py \
                   tests/unit/models/ \
                   tests/unit/workflow/"
        ;;
    priority2)
        echo -e "${BLUE}📋 Running: Priority 2 Tests (Server/API Layer)${NC}"
        TEST_PATH="tests/integration/test_api_files.py \
                   tests/integration/test_api_jobs.py \
                   tests/integration/test_api_analysis.py \
                   tests/integration/test_api_notebooks.py \
                   tests/unit/services/"
        ;;
    workflow)
        echo -e "${BLUE}📋 Running: Workflow Tests${NC}"
        TEST_PATH="tests/unit/workflow/"
        COVERAGE_FLAGS="--cov=src/workflow --cov-report=term-missing"
        ;;
    models)
        echo -e "${BLUE}📋 Running: Model Tests${NC}"
        TEST_PATH="tests/unit/models/"
        COVERAGE_FLAGS="--cov=src/models --cov-report=term-missing"
        ;;
    agents)
        echo -e "${BLUE}📋 Running: Agent Tests${NC}"
        TEST_PATH="tests/unit/agents/"
        COVERAGE_FLAGS="--cov=src/agents --cov-report=term-missing"
        ;;
    services)
        echo -e "${BLUE}📋 Running: Service Tests${NC}"
        TEST_PATH="tests/unit/services/"
        COVERAGE_FLAGS="--cov=src/server/services --cov-report=term-missing"
        ;;
    notebooks)
        echo -e "${BLUE}📋 Running: Notebook API Tests${NC}"
        TEST_PATH="tests/integration/test_api_notebooks.py"
        COVERAGE_FLAGS="--cov=src/server/routes/notebooks --cov-report=term-missing"
        ;;
    notebook-execution)
        echo -e "${BLUE}📋 Running: Live Notebook Execution Tests${NC}"
        TEST_PATH="tests/unit/services/ \
                   tests/integration/test_api_notebooks.py \
                   tests/unit/test_orchestrator.py::TestOrchestratorV170 \
                   tests/unit/test_orchestrator.py::TestOrchestratorModeAliases"
        COVERAGE_FLAGS="--cov=src/services --cov=src/server/routes/notebooks --cov-report=term-missing"
        ;;
    multi-file)
        echo -e "${BLUE}📋 Running: Multi-File Tests${NC}"
        TEST_PATH="tests/services/ \
                   tests/agents/test_profiler_multifile.py \
                   tests/agents/test_tuning_codegen.py \
                   tests/server/routes/test_templates.py \
                   tests/e2e/test_multifile_workflow.py \
                   tests/services/test_data_loader.py \
                   tests/services/test_join_detector.py"
        COVERAGE_FLAGS="--cov=src/services/data_loader --cov=src/services/join_detector --cov=src/services/template_manager --cov=src/server/routes/templates --cov-report=term-missing"
        ;;
    templates)
        echo -e "${BLUE}📋 Running: Template Management Tests${NC}"
        TEST_PATH="tests/services/test_template_manager.py \
                   tests/services/test_dictionary_manager.py \
                   tests/server/routes/test_templates.py"
        COVERAGE_FLAGS="--cov=src/services/template_manager --cov=src/server/routes/templates --cov-report=term-missing"
        ;;
    e2e)
        echo -e "${BLUE}📋 Running: End-to-End Workflow Tests${NC}"
        TEST_PATH="tests/e2e/"
        COVERAGE_FLAGS="--cov=src --cov-report=term-missing"
        ;;
    advanced-features)
        echo -e "${BLUE}📋 Running: Advanced Features Tests (Dimensionality, Quality)${NC}"
        TEST_PATH="tests/unit/test_quality_and_dimensionality.py \
                   tests/verify_quality_and_dimensionality.py"
        COVERAGE_FLAGS="--cov=src/agents/phase1/data_profiler --cov=src/agents/phase2/dimensionality_strategy --cov=src/models/handoffs --cov-report=term-missing"
        ;;
    *)
        echo -e "${RED}❌ Unknown test suite: $TEST_SUITE${NC}"
        show_help
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}🔧 Configuration:${NC}"
echo "  Test Suite: $TEST_SUITE"
echo "  Coverage Threshold: ${COVERAGE_THRESHOLD}%"
echo "  HTML Report: $HTML_REPORT"
[ -n "$VERBOSE" ] && echo "  Verbose: Yes"
[ -n "$QUICK" ] && echo "  Quick Mode: Yes"
echo ""

# Run tests
echo -e "${BLUE}🚀 Running Tests...${NC}"
echo "-------------------------------------------"
echo ""

# UI tests have different execution pattern
if [ "$TEST_SUITE" = "ui" ]; then
    $PYTEST_CMD $TEST_PATH \
        $UI_FLAGS \
        $VERBOSE \
        --tb=short
else
    $PYTEST_CMD $TEST_PATH \
        $COVERAGE_FLAGS \
        --cov-fail-under=$COVERAGE_THRESHOLD \
        $VERBOSE \
        $QUICK \
        --tb=short
fi

EXIT_CODE=$?

echo ""
echo "-------------------------------------------"

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ All Tests Passed!${NC}"
    echo ""

    if [ "$HTML_REPORT" = true ]; then
        echo -e "${BLUE}📊 HTML Coverage Report:${NC}"
        echo "  Open: htmlcov/index.html"
        echo ""
    fi

    # Display quick stats
    echo -e "${BLUE}📈 Quick Stats:${NC}"
    TEST_COUNT=$(find tests -name "test_*.py" -type f | wc -l)
    echo "  Total Test Files: $TEST_COUNT"

    # Count test functions (approximate)
    TOTAL_TESTS=$(grep -rh "def test_" tests/ 2>/dev/null | wc -l)
    echo "  Total Test Functions: ~$TOTAL_TESTS"

    echo ""
    echo -e "${GREEN}🎉 Test Suite Complete!${NC}"
else
    echo -e "${RED}❌ Tests Failed${NC}"
    echo ""
    echo -e "${YELLOW}Troubleshooting:${NC}"
    echo "  1. Check test failures above"
    echo "  2. Run with -v flag for verbose output"
    echo "  3. Check coverage threshold (current: ${COVERAGE_THRESHOLD}%)"
    echo ""
fi

echo ""
echo -e "${BLUE}💡 Next Steps:${NC}"
echo "  • Run specific suite: ./run_tests.sh -s unit"
echo "  • Generate HTML report: ./run_tests.sh --html"
echo "  • View coverage docs: cat tests/TEST_COVERAGE_SUMMARY.md"
echo ""

exit $EXIT_CODE
