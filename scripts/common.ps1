# Inzyts Common PowerShell Utilities
# Dot-source this file in other scripts: . "$PSScriptRoot\common.ps1"

# ==============================================================================
# Python Detection
# ==============================================================================
function Find-Python {
    if (Get-Command python3 -ErrorAction SilentlyContinue) {
        return "python3"
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        return "python"
    }
    else {
        return ""
    }
}

function Find-Pip {
    if ($env:VIRTUAL_ENV) {
        return Join-Path $env:VIRTUAL_ENV "Scripts\pip.exe"
    }
    elseif (Test-Path ".venv\Scripts\pip.exe") {
        return ".\.venv\Scripts\pip.exe"
    }
    else {
        return "pip"
    }
}

function Find-Pytest {
    if ($env:VIRTUAL_ENV) {
        return Join-Path $env:VIRTUAL_ENV "Scripts\pytest.exe"
    }
    elseif (Test-Path ".venv\Scripts\pytest.exe") {
        return ".\.venv\Scripts\pytest.exe"
    }
    else {
        return "pytest"
    }
}

# ==============================================================================
# Utility Functions
# ==============================================================================

function Write-Header {
    param([string]$Title)
    Write-Host "`n$Title" -ForegroundColor Blue -NoNewline
    Write-Host ""
    Write-Host "==================================" -ForegroundColor Blue
    Write-Host ""
}

function Write-Step {
    param([int]$Step, [int]$Total, [string]$Message)
    Write-Host "[$Step/$Total] $Message" -ForegroundColor Green
}

function Write-Success {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Red
}

function Write-Warning {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Blue
}

function Test-Service {
    param([string]$Url, [string]$Name)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        Write-Host "$Name running at $Url" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "$Name not running at $Url" -ForegroundColor Red
        return $false
    }
}
