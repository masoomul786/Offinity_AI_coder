#!/bin/bash
# Offinity_AI launcher
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "  ⚡ Offinity_AI"
echo "  ─────────────────"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "  ✗ Python 3 not found. Install from https://python.org"
    exit 1
fi

PYTHON=python3

# Install deps if needed
if ! $PYTHON -c "import requests" 2>/dev/null; then
    echo "  → Installing dependencies..."
    $PYTHON -m pip install -r requirements.txt -q
fi

# Copy .env if not exists
if [ ! -f .env ] && [ -f .env.example ]; then
    echo "  → Creating .env from example..."
    cp .env.example .env
    echo "  ℹ  Edit .env to configure your LLM provider"
fi

echo ""

# Check for --web flag
if [[ "$*" == *"--web"* ]] || [[ "$*" == *"-w"* ]]; then
    echo "  🌐 Starting Web UI..."
    $PYTHON main.py --web
else
    $PYTHON main.py "$@"
fi
