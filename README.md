# Bird's Eye

Web application for searching through video datasets using fuzzy text search, semantic embedding search, and per-video statistics with histogram filtering.

**This README covers:** how to run the processor, how to run the server, all API endpoints, the plugin architecture (including plugin-driven aggregation), multi-machine safety, and how processing feeds live data into the server.

## Quick Start

```bash
bash setup.sh                        # Install system deps + uv lock
bash process.sh --batch_size=500      # Process all videos
bash run.sh                           # Build frontend + aggregate + start server on port 8899
```

## Processing Pipeline

```
compress (Compression Ladder)       ← root, no dependencies
└── ingest (Ingest)                 ← thumbnails, sprites, metadata from 480p proxy
    ├── clip (CLIP Embeddings)      ← GPU, subprocess-isolated, all GPUs
    ├── phash (Perceptual Hash)     ← CPU-only, fast
    └── raft_flow (Optical Flow)    ← GPU, subprocess-isolated, all GPUs
```

Dependencies resolve automatically. Running `--process=ingest` also runs `compress` because ingest depends on it.

### How Processing Works

1. **Batch loop**: Videos are processed in batches (default 500). Each batch runs all enabled processors in dependency order.
2. **Skip what's done**: Each processor checks which videos already have its artifacts and skips them. Re-running is safe and incremental.
3. **Prerequisite priority sorting**: After shuffle, videos are stable-sorted by how many processors have their dependencies already satisfied (descending). Videos that are most ready to process come first, maximizing throughput. A tier breakdown is printed at startup.
4. **Shuffle for multi-machine safety**: `--shuffle` (default: on) randomizes processing order so multiple machines can run the same command without colliding.
5. **Auto-aggregation**: After each batch, the aggregator runs automatically (`--auto_aggregate`, default: on) so the server can pick up new data incrementally.
6. **Per-sample directories**: All artifacts for a video live in one directory (`datasets/<name>/samples/<shard>/<sample_id>/`). No shared mutable state between machines during processing.

### Processing Commands

```bash
# Process specific steps (+ their dependencies)
bash process.sh --process=ingest,phash --batch_size=500

# Skip GPU-heavy processors
bash process.sh --skip=clip,raft_flow

# All processors, shuffled (default)
bash process.sh --batch_size=500

# Disable auto-aggregation
bash process.sh --batch_size=500 --auto_aggregate=False

# Just rebuild the cache (no processing)
bash process.sh --aggregate_only

# Process sequentially (for debugging)
bash process.sh --batch_size=500 --shuffle=False
```

## Running the Server

```bash
bash run.sh              # Builds frontend, runs aggregator, starts server on port 8899
bash run.sh 9000         # Custom port
```

### Server API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve the web UI (Svelte SPA from `static/`) |
| `/api/datasets` | GET | List datasets with counts, available vector indices |
| `/api/search/fuzzy` | GET | FZF extended-mode text search through captions. Params: `dataset`, `q`, `limit`, `min_*`/`max_*` filters |
| `/api/search/clip` | GET | CLIP semantic search. Params: `dataset`, `q`, `limit`, `index` (default "clip"), `min_*`/`max_*` filters |
| `/api/search/hull` | POST | Convex hull (centroid) search from selected videos. Body: `{dataset, selected, limit, index}` |
| `/api/metadata_stats/<dataset>` | GET | Min/max ranges for all numeric fields (for filter sliders) |
| `/api/histograms/<dataset>` | GET | Histogram bin counts for all numeric fields. Params: `bins` (default 60) |
| `/api/field_info` | GET | Field descriptions and artifact metadata from all processor plugins |
| `/api/config` | GET | Shared constants (sprite grid dimensions) |
| `/api/status/<dataset>` | GET | Data counts for reload-available detection. Includes per-vector-index counts |
| `/api/reload/<dataset>` | GET | Hot-reload cache without restarting the server process |
| `/api/video_info/<dataset>/<video_name>` | GET | Full video details: metadata, stats, thumbnail URLs, video URL |
| `/api/video/<dataset>/<video_name>` | GET | Stream the original video file for playback |
| `/thumbnails/<dataset>/<video_name>/<file>` | GET | Serve per-sample files with transparent shard routing |

### Live Data Updates

The server reads from `datasets/<name>/cache/`, which is built by the aggregator from per-sample artifacts. The flow is:

1. **Processing** creates per-sample artifacts in `samples/` (incremental, safe to run while server is up)
2. **Auto-aggregation** runs after each batch, scanning `samples/` and building cache files (FAISS index, merged JSON)
3. **Server** reads from `cache/` at startup; can hot-reload via `/api/reload/<dataset>` without restart
4. **Frontend** polls `/api/status/<dataset>` and shows "Reload available" when data counts change

To manually update the server with newly processed data:
```bash
uv run python preprocess/aggregator.py --dataset_dir datasets/pexels  # rebuild cache
# Then reload in browser, or hit /api/reload/pexels
```

## Processor Plugins

Each processor is one `.py` file in `preprocess/processors/`. Drop a file, it auto-registers. No changes to any other file needed.

**Plugins are the sole source of truth** for all fields, filter labels, sort options, descriptions, and aggregation rules. The frontend, server, and aggregator never hardcode field names — they query the plugins and render dynamically.

| Processor | Depends On | Artifacts | Fields | Aggregation | Description |
|-----------|-----------|-----------|--------|-------------|-------------|
| **compress** | — | 6 proxy videos (1080p–144p) | — | — | H.264 veryfast CRF 28 proxy ladder. Single-decode 6-output cascade. |
| **ingest** | compress | `thumb_{first,middle,last}.jpg`, `sprite.jpg`, `metadata.json` | width, height, fps, num_frames, duration, file_size_mb | json_dict → video_metadata.json | Thumbnails (512px), sprite sheet (5x5), video metadata. Reads from 480p proxy. |
| **clip** | ingest | `clip_{embedding,first,last}.npy`, `clip_std.json` | clip_std | json_dict → video_stats.json, vector_index "clip" (512-dim FAISS) | CLIP ViT-B/32 embeddings. All GPUs, subprocess-isolated. |
| **phash** | ingest | `phash_stats.json` | phash_mean_change, phash_max_change, phash_std_change, phash_temporal_std | json_dict → video_stats.json | Perceptual hash distances between sprite frames. CPU-only. |
| **raft_flow** | ingest | `flow_stats.json` | flow_mean_magnitude, flow_max_magnitude, flow_min_magnitude, flow_std_magnitude, flow_temporal_std | json_dict → video_stats.json | RAFT optical flow statistics. All GPUs, subprocess-isolated. |

### Plugin-Driven Aggregation

Each processor declares how its per-sample data should be aggregated into cache files via the `aggregation` class attribute. Two types:

- **`json_dict`**: Merge per-sample JSON files into `{video_name: data}` dicts. Multiple processors can target the same cache file (e.g., clip, phash, raft_flow all write to `video_stats.json`).
- **`vector_index`**: Read per-sample `.npy` vectors, concatenate, build FAISS `IndexFlatIP`. Generates `{prefix}_embeddings.npz`, `{prefix}_index.faiss`, `{prefix}_names.json`. Generic — any processor can declare an embedding that gets FAISS-indexed.

The aggregator reads these rules from plugins. No hardcoded file paths.

### Adding a New Processor

1. Create `preprocess/processors/my_analysis.py`
2. Subclass `Processor`, define `name`, `human_name`, `depends_on`, `artifacts`, `fields`
3. Define `aggregation` rules (optional — tells the aggregator how to cache your data)
4. Implement `process(entries, dataset_dir, workers)` — processes ONLY given entries
5. Add Fire CLI at bottom: `fire.Fire({"main": main})`
6. Done — auto-discovered, collision-validated, fields appear in UI, data aggregated

## Sample Directory Layout

Each video gets a self-contained directory with all its artifacts:

```
datasets/pexels/samples/1b/e5/pexels_19012581/
├── origins.json              # Source metadata
├── video.mp4                 # Symlink to original source
├── compress_1080p.mp4        # Proxy video
├── compress_480p.mp4         # Primary proxy (10x decode speedup)
├── compress_144p.mp4         # Miniature proxy
├── thumb_first.jpg           # 512px height, first frame
├── thumb_middle.jpg          # 512px height, middle frame (primary display)
├── thumb_last.jpg            # 512px height, last frame
├── sprite.jpg                # 960x540, 5x5 grid, 25 frames at 192x108
├── metadata.json             # {width, height, fps, duration, num_frames, file_size_mb}
├── clip_embedding.npy        # float16 (512,), L2-normalized
├── clip_std.json             # {clip_std: float}
├── phash_stats.json          # {phash_mean_change, phash_max_change, ...}
└── flow_stats.json           # {flow_mean_magnitude, flow_max_magnitude, ...}
```

Directories are sharded by sha256 of the sample ID (65,536 buckets). The server routes thumbnail URLs transparently — `/thumbnails/pexels/19012581/thumb_middle.jpg` resolves to the correct shard path internally.

## Architecture

- **Frontend**: Svelte + Vite, built to `static/`, served by Flask
- **Server**: Flask REST API, reads from `cache/`, routes thumbnails through shard computation
- **Search**: FZF-style fuzzy text + CLIP cosine similarity + convex hull centroid in embedding space
- **Processing**: Modular plugin system with auto-discovery, dependency resolution, collision validation, prerequisite priority sorting
- **Aggregation**: Plugin-driven — each processor declares its aggregation rules, aggregator is a generic loop
- **Data**: Per-sample directories (multi-machine safe), aggregated cache (server-optimized)

Full specification in `claude_instructions.md`.
