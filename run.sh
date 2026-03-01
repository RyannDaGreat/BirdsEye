#!/bin/bash
set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

PORT="${1:-8899}"

# Ensure uv is available
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Ensure deps are locked
if [ ! -f "uv.lock" ]; then
    echo "Locking dependencies..."
    uv lock
fi

# Build frontend (Svelte → static/)
if [ -d "frontend" ]; then
    echo "Building frontend..."
    cd frontend
    if [ ! -d "node_modules" ]; then
        npm install
    fi
    npm run build
    cd "$REPO_ROOT"
    echo ""
fi

# Check if preprocessing has been done
if [ ! -f "datasets/pexels/manifest.json" ]; then
    echo "ERROR: No manifest found. Run preprocessing first:"
    echo "  bash preprocess/run_pipeline.sh"
    exit 1
fi

# Aggregate (build/update cache from samples)
echo "Aggregating cache..."
uv run python preprocess/aggregator.py --dataset_dir datasets/pexels
echo ""

# Count from cache manifest (fast, no NFS scan)
if [ -f "datasets/pexels/cache/cache_manifest.json" ]; then
    SAMPLE_COUNT=$(uv run python -c "import json; m=json.load(open('datasets/pexels/cache/cache_manifest.json')); print(m.get('total_samples',0))" 2>/dev/null || echo "0")
else
    SAMPLE_COUNT="0"
fi
echo "Bird's Eye"
echo "  Port:       http://0.0.0.0:${PORT}"
echo "  Dataset:    pexels"
echo "  Processed:  ${SAMPLE_COUNT} samples"
echo ""

if [ "$SAMPLE_COUNT" = "0" ]; then
    echo "WARNING: No processed samples found. Run: bash process.sh"
    echo "  Server will start but no images will display."
    echo ""
fi

uv run python server/app.py --port "$PORT"
