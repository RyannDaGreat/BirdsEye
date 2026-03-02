#!/bin/bash
set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

# Parse arguments: run.sh [PORT] [--skip-aggregate]
PORT=8899
SKIP_AGGREGATE=false
for arg in "$@"; do
    case "$arg" in
        -h|--help)
            echo "Usage: bash run.sh [PORT] [--skip-aggregate]"
            echo ""
            echo "  PORT              Server port (default: 8899)"
            echo "  --skip-aggregate  Skip cache aggregation for fast startup."
            echo "                    Errors if any dataset has no cached data."
            exit 0
            ;;
        --skip-aggregate) SKIP_AGGREGATE=true ;;
        [0-9]*)           PORT="$arg" ;;
        *)
            echo "ERROR: Unknown argument: $arg"
            echo "Try: bash run.sh --help"
            exit 1
            ;;
    esac
done

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

# Discover datasets with manifest.json
DATASETS=()
for d in datasets/*/manifest.json; do
    [ -f "$d" ] && DATASETS+=("$(dirname "$d")")
done

if [ ${#DATASETS[@]} -eq 0 ]; then
    echo "ERROR: No datasets found. Run preprocessing first:"
    echo "  uv run python preprocess/process_all.py --dataset <name>"
    exit 1
fi

# Aggregate or validate cache for each dataset
if [ "$SKIP_AGGREGATE" = true ]; then
    echo "Skip-aggregate: validating caches..."
    MISSING=()
    for ds_dir in "${DATASETS[@]}"; do
        if [ ! -f "$ds_dir/cache/cache_manifest.json" ]; then
            MISSING+=("$(basename "$ds_dir")")
        fi
    done
    if [ ${#MISSING[@]} -gt 0 ]; then
        echo "ERROR: --skip-aggregate was set but no cache found for: ${MISSING[*]}"
        echo ""
        echo "  Either run aggregation first (without --skip-aggregate),"
        echo "  or process the missing datasets:"
        for m in "${MISSING[@]}"; do
            echo "    uv run python preprocess/process_all.py --dataset $m"
        done
        exit 1
    fi
    echo "  All ${#DATASETS[@]} dataset(s) have cached data. Skipping aggregation."
    echo ""
else
    echo "Aggregating cache for ${#DATASETS[@]} dataset(s)..."
    for ds_dir in "${DATASETS[@]}"; do
        echo "  $(basename "$ds_dir")..."
        uv run python preprocess/aggregator.py --dataset_dir "$ds_dir"
    done
    echo ""
fi

# Summary
echo "Bird's Eye"
echo "  Port:       http://0.0.0.0:${PORT}"
echo "  Datasets:   ${#DATASETS[@]}"
for ds_dir in "${DATASETS[@]}"; do
    ds_name="$(basename "$ds_dir")"
    cache_file="$ds_dir/cache/cache_manifest.json"
    if [ -f "$cache_file" ]; then
        count=$(uv run python -c "import json; print(json.load(open('$cache_file')).get('total_samples',0))" 2>/dev/null || echo "0")
    else
        count=0
    fi
    echo "    $ds_name: $count samples"
done
echo ""

uv run python server/app.py --port "$PORT"
