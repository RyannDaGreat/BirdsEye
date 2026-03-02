#!/bin/bash
# Thin bootstrapper: ensures uv + lockfile exist, then delegates to Python.
# All logic (frontend build, aggregation, server) lives in server/app.py.
#
# Usage: bash run.sh [PORT] [--skip_aggregate]
#        bash run.sh startup --help
set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

# Ensure uv is available (must be bash — can't uv run without uv)
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Ensure deps are locked (must be bash — can't uv run without lockfile)
if [ ! -f "uv.lock" ]; then
    echo "Locking dependencies..."
    uv lock
fi

# Delegate everything else to Python (Fire handles --help, arg validation, etc.)
uv run python server/app.py startup "$@"
