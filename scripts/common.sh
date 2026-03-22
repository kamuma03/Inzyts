#!/bin/bash
# Inzyts Common Shell Utilities
# Source this file in other scripts: source "$(dirname "$0")/../scripts/common.sh"

# ==============================================================================
# ANSI Color Definitions
# ==============================================================================
export RED='\033[0;31m'
export GREEN='\033[0;32m'
export BLUE='\033[0;34m'
export YELLOW='\033[1;33m'
export BOLD='\033[1m'
export NC='\033[0m' # No Color

# ==============================================================================
# Python Detection
# ==============================================================================
detect_python() {
    if command -v python3 &> /dev/null; then
        echo "python3"
    elif command -v python &> /dev/null; then
        echo "python"
    else
        echo ""
    fi
}

# Detect pip and pytest respecting virtual environment
detect_pip() {
    if [[ -n "$VIRTUAL_ENV" ]]; then
        echo "$VIRTUAL_ENV/bin/pip"
    elif [[ -d ".venv" ]]; then
        echo "./.venv/bin/pip"
    else
        echo "pip"
    fi
}

detect_pytest() {
    if [[ -n "$VIRTUAL_ENV" ]]; then
        echo "$VIRTUAL_ENV/bin/pytest"
    elif [[ -d ".venv" ]]; then
        echo "./.venv/bin/pytest"
    else
        echo "pytest"
    fi
}

# ==============================================================================
# Utility Functions
# ==============================================================================

# Print section header
print_header() {
    local title="$1"
    echo -e "${BOLD}${BLUE}$title${NC}"
    echo "=================================="
    echo ""
}

# Print step indicator
print_step() {
    local step="$1"
    local total="$2"
    local message="$3"
    echo -e "${GREEN}[$step/$total] $message${NC}"
}

# Print success message
print_success() {
    echo -e "${GREEN}$1${NC}"
}

# Print error message
print_error() {
    echo -e "${RED}$1${NC}"
}

# Print warning message
print_warning() {
    echo -e "${YELLOW}$1${NC}"
}

# Print info message
print_info() {
    echo -e "${BLUE}$1${NC}"
}

# Check if a service is running (via curl)
check_service() {
    local url="$1"
    local name="$2"
    if curl -s "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}$name running at $url${NC}"
        return 0
    else
        echo -e "${RED}$name not running at $url${NC}"
        return 1
    fi
}
