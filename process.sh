#!/bin/bash
# Process videos. Passes all arguments to process_all.py.
#
# Usage:
#   bash process.sh --process=all                                # all processors
#   bash process.sh --process=clip --batch_size=500              # clip + deps only
#   bash process.sh --process=all --skip=raft_flow               # all except raft
#   bash process.sh --process=ingest,phash --batch_size=500      # specific processors
#   bash process.sh --process=all --auto_aggregate=False         # skip aggregation
#
# --process is REQUIRED. Use --process=all to run everything.
# Valid flags: --manifest, --dataset_dir, --batch_size, --workers,
#              --shuffle, --process, --skip, --auto_aggregate

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

uv run python preprocess/process_all.py "$@"
