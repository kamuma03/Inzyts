# Inzyts Application Starter (Windows PowerShell)
# Starts the full Docker stack (Backend + Frontend + DB + Redis + Jupyter)

$ErrorActionPreference = "Stop"

# Source common utilities
. "$PSScriptRoot\scripts\common.ps1"

# Force Python to flush print statements immediately
$env:PYTHONUNBUFFERED = "1"

Write-Header "Starting Inzyts Stack"

# ── Prerequisites check ─────────────────────────────────────────────────────

# Check Docker is available
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed. Please install Docker Desktop first:"
    Write-Info "  https://docs.docker.com/desktop/install/windows-install/"
    exit 1
}

try {
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "not running" }
}
catch {
    Write-Error "Docker daemon is not running. Please start Docker Desktop."
    exit 1
}

# Check Docker Compose
try {
    docker compose version 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "missing" }
}
catch {
    Write-Error "Docker Compose is not available. Please update Docker Desktop."
    exit 1
}

# ── First-run setup wizard ──────────────────────────────────────────────────

# Detect Python for the setup wizard
$PythonCmd = Find-Python
if (-not $PythonCmd) {
    Write-Error "Python 3 is required to run the setup wizard."
    Write-Info "  Install Python 3.10+ from https://www.python.org/downloads/windows/"
    exit 1
}

$wizardScript = Join-Path $PSScriptRoot "scripts\setup_wizard.py"

& $PythonCmd $wizardScript --check 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Warning "No .env file found - running first-time setup wizard..."
    Write-Host ""
    & $PythonCmd $wizardScript
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Setup wizard was cancelled or failed."
        exit 1
    }
}
else {
    Write-Success ".env file found - skipping setup wizard."
    Write-Info "  To reconfigure: python scripts\setup_wizard.py --force"
}

Write-Host ""

# ── Start Docker stack ──────────────────────────────────────────────────────

# Register cleanup handler for Ctrl+C
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
    Write-Host "Stopping services..." -ForegroundColor Yellow
    docker compose down
}

try {
    # 1. Start Full Stack
    Write-Step 1 2 "Starting Docker Stack (Backend + Frontend + DB + Redis)..."
    docker compose up -d --build --force-recreate

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to start services."
        exit 1
    }

    # 2. Stream Logs
    Write-Step 2 2 "Streaming logs..."
    Write-Info "Backend:  http://localhost:8000"
    Write-Info "Frontend: http://localhost:5173"
    Write-Host "Press Ctrl+C to stop services."

    docker compose logs -f
}
finally {
    Write-Warning "Shutting down services..."
    docker compose down
}
