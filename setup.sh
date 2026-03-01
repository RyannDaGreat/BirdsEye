#!/bin/bash
set -e

# System dependencies
apt-get update && apt-get install -y ffmpeg

# Install uv if not present
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Resolve and lock Python dependencies
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"
uv lock

echo "Setup complete. Run: bash run.sh"
