# Comprehensive Test Runner for Inzyts (Windows PowerShell)
# Purpose: Run all tests with coverage reporting and quality checks

param(
    [Alias("s")]
    [string]$Suite = "all",

    [Alias("t")]
    [int]$Threshold = 95,

    [Alias("v")]
    [switch]$Verbose,

    [switch]$Html,

    [switch]$Quick,

    [switch]$Headed,

    [Alias("h")]
    [switch]$Help
)

$ErrorActionPreference = "Stop"

# Source common utilities
. "$PSScriptRoot\..\scripts\common.ps1"

if ($Help) {
    Write-Host @"

Inzyts Test Runner (PowerShell)

Usage:
  .\run_tests.ps1 [options]

Options:
  -h, -Help               Show this help message
  -s, -Suite SUITE        Test suite to run: all, unit, integration, performance, ui
  -t, -Threshold NUM      Coverage threshold percentage (default: 95)
  -v, -Verbose            Verbose output
  -Html                   Generate HTML coverage report
  -Quick                  Quick test (skip slow tests)
  -Headed                 Run UI tests in headed mode (for debugging)

Examples:
  .\run_tests.ps1                            # Run all tests
  .\run_tests.ps1 -s unit                    # Run only unit tests
  .\run_tests.ps1 -s integration -v          # Run integration tests with verbose output
  .\run_tests.ps1 -Html -Threshold 85        # Generate HTML report with 85% threshold
  .\run_tests.ps1 -Quick                     # Quick test run

Test Suites:
  all, unit, integration, db, performance, ui,
  priority1, priority2, workflow, models, agents,
  services, notebooks, notebook-execution, multi-file,
  templates, e2e, advanced-features
"@
    exit 0
}

Write-Host ""
Write-Host "Inzyts Test Suite" -ForegroundColor Blue
Write-Host "==================================" -ForegroundColor Blue
Write-Host ""

# Check if pytest is installed
if (-not (Get-Command pytest -ErrorAction SilentlyContinue)) {
    Write-Warning "pytest not found. Installing..."
    pip install pytest pytest-cov pytest-mock
}

# Build pytest command based on suite
$PytestCmd = "pytest"
$CoverageFlags = "--cov=src --cov-report=term-missing"
$VerboseFlag = ""
$QuickFlag = ""
$TestPath = ""
$UiFlags = ""

if ($Verbose) { $VerboseFlag = "-vv" }
if ($Quick) { $QuickFlag = "-m 'not slow'" }
if ($Html) { $CoverageFlags += " --cov-report=html" }

switch ($Suite) {
    "all" {
        Write-Info "Running: All Tests"
        $TestPath = "tests/"
    }
    "unit" {
        Write-Info "Running: Unit Tests"
        $TestPath = "tests/unit/"
    }
    "integration" {
        Write-Info "Running: Integration Tests"
        $TestPath = "tests/integration/"
    }
    "db" {
        Write-Info "Running: Real Database Tests (testcontainers)"
        if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
            Write-Error "Docker is required for database tests but is not available."
            exit 1
        }
        $TestPath = "tests/integration/test_sql_real_db.py"
        $PytestCmd = "pytest -m requires_db"
        $CoverageFlags = "--cov=src/server/services/data_ingestion --cov=src/agents/sql_agent --cov-report=term-missing"
    }
    "performance" {
        Write-Info "Running: Performance Tests"
        $TestPath = "tests/performance/"
    }
    "ui" {
        Write-Info "Running: UI Tests (Playwright)"

        $PipCmd = Find-Pip
        $PythonCmd = Find-Python

        Write-Info "Installing Playwright dependencies..."
        & $PipCmd install pytest-playwright --quiet
        & $PythonCmd -m playwright install chromium

        Write-Info "Checking if application is running..."
        $frontendOk = Test-Service "http://localhost:5173" "Frontend"
        $backendOk = Test-Service "http://localhost:8000/health" "Backend"

        if (-not $frontendOk) {
            Write-Error "Frontend is not running. Start the app first: .\start_app.ps1"
            exit 1
        }
        if (-not $backendOk) {
            Write-Warning "Backend not running. UI tests may fail."
        }

        $TestPath = "tests/ui/"
        $UiFlags = "--base-url http://localhost:5173 --slowmo 500"
        if ($Headed) { $UiFlags += " --headed" }
        $CoverageFlags = ""
    }
    "priority1" {
        Write-Info "Running: Priority 1 Tests (Core Infrastructure)"
        $TestPath = "tests/unit/agents/test_base_agent.py tests/unit/agents/phase1/test_profile_codegen.py tests/unit/agents/phase2/test_analysis_codegen_methods.py tests/unit/agents/phase2/test_analysis_validator_full.py tests/unit/models/ tests/unit/workflow/"
    }
    "priority2" {
        Write-Info "Running: Priority 2 Tests (Server/API Layer)"
        $TestPath = "tests/integration/test_api_files.py tests/integration/test_api_jobs.py tests/integration/test_api_analysis.py tests/integration/test_api_notebooks.py tests/unit/services/"
    }
    "workflow" {
        Write-Info "Running: Workflow Tests"
        $TestPath = "tests/unit/workflow/"
        $CoverageFlags = "--cov=src/workflow --cov-report=term-missing"
    }
    "models" {
        Write-Info "Running: Model Tests"
        $TestPath = "tests/unit/models/"
        $CoverageFlags = "--cov=src/models --cov-report=term-missing"
    }
    "agents" {
        Write-Info "Running: Agent Tests"
        $TestPath = "tests/unit/agents/"
        $CoverageFlags = "--cov=src/agents --cov-report=term-missing"
    }
    "services" {
        Write-Info "Running: Service Tests"
        $TestPath = "tests/unit/services/"
        $CoverageFlags = "--cov=src/server/services --cov-report=term-missing"
    }
    "e2e" {
        Write-Info "Running: End-to-End Workflow Tests"
        $TestPath = "tests/e2e/"
        $CoverageFlags = "--cov=src --cov-report=term-missing"
    }
    default {
        Write-Error "Unknown test suite: $Suite"
        exit 1
    }
}

Write-Host ""
Write-Info "Configuration:"
Write-Host "  Test Suite: $Suite"
Write-Host "  Coverage Threshold: $Threshold%"
Write-Host "  HTML Report: $Html"
if ($Verbose) { Write-Host "  Verbose: Yes" }
if ($Quick) { Write-Host "  Quick Mode: Yes" }
Write-Host ""

Write-Info "Running Tests..."
Write-Host "-------------------------------------------"
Write-Host ""

# Build and execute the command
$cmdArgs = @($TestPath)
if ($Suite -eq "ui") {
    if ($UiFlags) { $cmdArgs += $UiFlags.Split(" ") }
}
else {
    if ($CoverageFlags) { $cmdArgs += $CoverageFlags.Split(" ") }
    $cmdArgs += "--cov-fail-under=$Threshold"
}
if ($VerboseFlag) { $cmdArgs += $VerboseFlag }
if ($QuickFlag) { $cmdArgs += $QuickFlag }
$cmdArgs += "--tb=short"

& $PytestCmd @cmdArgs

$exitCode = $LASTEXITCODE

Write-Host ""
Write-Host "-------------------------------------------"

if ($exitCode -eq 0) {
    Write-Success "All Tests Passed!"
    if ($Html) {
        Write-Info "HTML Coverage Report: Open htmlcov\index.html"
    }
}
else {
    Write-Error "Tests Failed"
    Write-Host ""
    Write-Warning "Troubleshooting:"
    Write-Host "  1. Check test failures above"
    Write-Host "  2. Run with -v flag for verbose output"
    Write-Host "  3. Check coverage threshold (current: $Threshold%)"
}

Write-Host ""
Write-Info "Next Steps:"
Write-Host "  - Run specific suite: .\run_tests.ps1 -s unit"
Write-Host "  - Generate HTML report: .\run_tests.ps1 -Html"
Write-Host ""

exit $exitCode
