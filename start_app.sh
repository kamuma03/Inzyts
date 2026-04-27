#!/bin/bash
# Inzyts Application Starter
# Starts the full Docker stack (Backend + Frontend + DB + Redis + Worker)
# Live notebook execution runs in-process inside the Worker container via
# KernelSandbox (PR1) — no separate Jupyter Server is needed.

set -e

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/scripts/common.sh"

# Force Python to flush print statements immediately
export PYTHONUNBUFFERED=1

print_header "Starting Inzyts Stack"

# ── Prerequisites check ──────────────────────────────────────────────────────

# Check Docker is available
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker Desktop first:"
    print_info "  https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker info &> /dev/null 2>&1; then
    print_error "Docker daemon is not running. Please start Docker Desktop."
    exit 1
fi

# Check Docker Compose
if ! docker compose version &> /dev/null 2>&1; then
    print_error "Docker Compose is not available. Please install Docker Compose:"
    print_info "  https://docs.docker.com/compose/install/"
    exit 1
fi

# ── First-run setup wizard ───────────────────────────────────────────────────

# Detect Python for the setup wizard
PYTHON_CMD=$(detect_python)
if [ -z "$PYTHON_CMD" ]; then
    print_error "Python 3 is required to run the setup wizard."
    print_info "  Install Python 3.10+ from https://www.python.org/downloads/"
    exit 1
fi

if ! $PYTHON_CMD "$SCRIPT_DIR/scripts/setup_wizard.py" --check 2>/dev/null; then
    print_warning "No .env file found — running first-time setup wizard..."
    echo ""
    $PYTHON_CMD "$SCRIPT_DIR/scripts/setup_wizard.py"
    WIZARD_EXIT=$?
    if [ $WIZARD_EXIT -ne 0 ]; then
        print_error "Setup wizard was cancelled or failed."
        exit 1
    fi
else
    print_success ".env file found — skipping setup wizard."
    print_info "  To reconfigure: python scripts/setup_wizard.py --force"
fi

echo ""

# ── Start Docker stack ───────────────────────────────────────────────────────

# Function to kill child processes on exit
cleanup() {
    print_error "Stopping log stream and shutting down services..."
    docker compose down
    exit
}

# Trap SIGINT (Ctrl+C) and SIGTERM
trap cleanup SIGINT SIGTERM

# 1. Start Full Stack
print_step 1 2 "Starting Docker Stack (Backend + Frontend + DB + Redis)..."
# Use --build to ensure changes are picked up, and --force-recreate to ensure fresh containers
docker compose up -d --build --force-recreate

if [ $? -ne 0 ]; then
    print_error "Failed to start services."
    exit 1
fi

# 2. Stream Logs
print_step 2 2 "Streaming logs..."
print_info "Backend:  http://localhost:8000"
print_info "Frontend: http://localhost:5173"
echo "Press Ctrl+C to stop services."

docker compose logs -f
