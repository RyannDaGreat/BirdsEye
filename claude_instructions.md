# Searchable Pexels — Project Manifest (v2: Processor Architecture)

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!!! NON-NEGOTIABLE: MANIFEST-FIRST DEVELOPMENT                                !!!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

**Before ANY code change, update this manifest FIRST.**

1. **Plan in the manifest** — describe WHAT you're building and HOW before writing code
2. **DRY is sacred** — never duplicate code. If you see duplication, refactor first.
3. **Functional style** — pure functions, minimal state, no side effects where avoidable
4. **This manifest = the project** — a fresh session must be able to recreate everything
   from this document alone. If it's not documented here, it doesn't exist.
5. **Even if the user asks you to "just do it"** — update the manifest first. Always.

If the codebase and the manifest disagree, the manifest is wrong and must be fixed,
OR the code is wrong and must be fixed. They must NEVER be out of sync.

## Development Philosophy

- **DRY above all else.** Never duplicate code, CSS, or logic. If two things look similar, they must share an abstraction.
- **Composition over inheritance over copy-paste.**
- **Functional programming.** Pure functions, minimal state, well-documented with doctests. Label pure functions as such. Separate computation from I/O.
- **General-purpose pure functions.** Pure functions should be mathematically general and reusable, not hyperspecific to one use case. The bulk of computation lives in general functions; domain-specific glue is thin.
- **Minimal CSS.** One shared class for one purpose. If a style appears twice, it's a bug. Explicit dimensions. No magic numbers — all from CSS custom properties.
- **Icons: Iconify only.** Always use `<iconify-icon>` for icons. Never use Unicode symbols, emoji, or inline SVG for icons. All icon names use `mdi:*` prefix (Material Design Icons via Iconify CDN).
- **No silent fallbacks.** If something fails, show an error. Never silently degrade.
- **Every interactive element MUST have a tooltip.**
- **Modular and pluggable.** New processors = drop a .py file. Zero changes elsewhere.
- **Messy requirements in, clean code out.**
- **Talk while working.** Never silently implement.
- **All requirements go in the manifest.**
- **No backward compatibility cruft.** This is v2. No low-res thumbnails, no quality toggle, no fallback paths for old data formats. One resolution, one format, clean.

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

## Goal

A self-contained web application for searching through video datasets using:
1. **FZF-style fuzzy text search** through video captions
2. **CLIP semantic search** through pre-computed image embeddings via FAISS
3. **Selection-based refinement** — select videos, then search within / around them (convex hull)
4. **Export** — copy video names as newline-separated text
5. **Filterable by any numeric field** — histogram range selectors with draggable handles
6. **Sortable by any field** — ascending/descending toggle, random shuffle
7. **Pluggable processing** — add new analyses by dropping a Python file

## Architecture Overview

### Core Principle: Processors

Everything that extracts or computes data from videos is a **processor module**. Each processor is a Python file in `preprocess/processors/` that subclasses `Processor`. Processors are auto-discovered — adding a new one requires zero changes to any other file.

### Core Principle: Per-Sample Directories

Every video sample has one directory containing ALL its artifacts. The directory is self-contained: `origins.json` (raw source data), `video.mp4` (symlink to source), and all generated files. You can `ls` a sample dir and see everything about that video.

### Core Principle: Cache = Derived from Samples

Aggregated files (FAISS index, merged metadata) live in `cache/` and are always regenerable from samples. Deleting `cache/` loses nothing.

### Core Principle: No Backward Compatibility

This is a clean redesign. There are no low-res thumbnails, no quality toggle, no fallback paths. Every thumbnail is HQ (512px height). The sprite sheet is the only small-resolution artifact (192x108 cells, needed for hover animation). The frontend has no concept of "small vs HQ" — there's just one resolution per artifact type.

## Data Structure

```
datasets/pexels/
  manifest.json                          # Input: [{video_name, caption, source_path}, ...]

  samples/                               # Per-sample artifacts, two-level sha256 sharded
    ae/                                  # sha256(sample_id)[:2]
      d3/                                # sha256(sample_id)[2:4]
        pexels_19012581/                 # sample_id = "{dataset}_{video_name}" (globally unique)
          origins.json                   # {video_name, caption, source_path, dataset}
          video.mp4 → symlink            # Symlink to original source video

          # === compress processor (root, no deps) ===
          compress_1080p.mp4             # H.264 veryfast CRF 28, smaller dim ≤ 1080px
          compress_720p.mp4              # smaller dim ≤ 720px
          compress_480p.mp4              # smaller dim ≤ 480px (primary proxy, 10x decode speedup)
          compress_360p.mp4              # smaller dim ≤ 360px
          compress_240p.mp4              # smaller dim ≤ 240px
          compress_144p.mp4              # smaller dim ≤ 144px (miniature thumbnail video)

          # === ingest processor (depends on compress) ===
          thumb_first.jpg                # 512px height, first frame, from 480p proxy
          thumb_middle.jpg               # 512px height, middle frame (primary display image)
          thumb_last.jpg                 # 512px height, last frame
          sprite.jpg                     # 960x540, 5x5 grid, 25 frames at 192x108 contain-padded
          metadata.json                  # {width, height, fps, num_frames, duration, file_size_mb} (from ORIGINAL)

          # === clip processor ===
          clip_embedding.npy             # float16 (512,), L2-normalized, from thumb_middle.jpg
          clip_first.npy                 # float16 (512,), from thumb_first.jpg
          clip_last.npy                  # float16 (512,), from thumb_last.jpg
          clip_std.json                  # {clip_std: 0.0154}

          # === raft_flow processor ===
          flow_stats.json                # {flow_mean_magnitude, flow_max_magnitude, flow_min_magnitude, flow_std_magnitude, flow_temporal_std}

          # === phash processor ===
          phash_stats.json               # {phash_mean_change, phash_max_change, phash_std_change, phash_temporal_std}

    f3/
      7b/
        pexels_3205486/
          ... (same structure)

  cache/                                 # Aggregated from samples/, fully regenerable
    clip_embeddings.npz                  # (N, 512) float16 matrix
    clip_index.faiss                     # FAISS IndexFlatIP
    clip_names.json                      # Ordered names aligned with FAISS rows
    video_metadata.json                  # {name: {width, height, fps, ...}} merged
    video_stats.json                     # {name: {clip_std, flow_mean_magnitude, ...}} merged
    cache_manifest.json                  # {samples_included: [...], timestamp: "..."}
```

### Sample ID and Two-Level Shard Function

Sample IDs are globally unique: `{dataset}_{video_name}` (e.g., `pexels_19012581`). This prevents collisions between datasets that might share numeric video names (e.g., Pexels `118272` vs Envato `118272`).

The shard is computed from the full sample ID, not just the video name.

```python
import hashlib, os

def sample_id(dataset, video_name):
    """
    Globally unique sample identifier.
    Pure function.

    >>> sample_id("pexels", "19012581")
    'pexels_19012581'
    """
    return f"{dataset}_{video_name}"

def sample_shard(sid):
    """
    Two-level shard from sha256 of sample_id.
    Returns 'ab/cd' path component.
    65,536 buckets. ~1.2 per bucket at 81K, ~152 at 10M.
    Pure function.
    """
    h = hashlib.sha256(sid.encode()).hexdigest()
    return os.path.join(h[:2], h[2:4])

def sample_dir(dataset_dir, video_name):
    """Full path to sample directory. Pure function."""
    dataset = os.path.basename(dataset_dir)
    sid = sample_id(dataset, video_name)
    return os.path.join(dataset_dir, "samples", sample_shard(sid), sid)
```

### origins.json

```json
{
  "video_name": "19012581",
  "caption": "A serene lake surrounded by mountains...",
  "source_path": "/root/CleanCode/Datasets/Pexels/downloads/19/19012581.mp4",
  "dataset": "pexels"
}
```

### video.mp4 Link

Hardlink from `<sample_dir>/video.mp4` to the source video, with symlink fallback if hardlink fails (e.g., across filesystems). Every processor reads from this link, never from the manifest directly.

### Thumbnail Naming: No "small" vs "HQ"

v1 had `first.jpg` (192x108) and `hq_first.jpg` (512px). v2 has only `thumb_first.jpg` (512px). The word "thumb" distinguishes it from the sprite sheet cells. There is no small resolution — 512px height is the only thumbnail resolution. The frontend displays these directly with CSS `object-fit: contain`.

The sprite sheet cells (192x108) are the only small images, and they exist only inside `sprite.jpg` — not as individual files.

## Processor Base Class

File: `preprocess/processors/base.py`

Uses Python's `abc.ABC` and `@abstractmethod` to enforce the plugin contract at class definition time.
Uses `__init_subclass__` to validate that `name` and `human_name` are defined.

```python
from abc import ABC, abstractmethod

class Processor(ABC):
    name: str              # Machine name: "ingest", "clip" — enforced by __init_subclass__
    human_name: str        # Display name: "Ingest", "CLIP Embeddings" — enforced by __init_subclass__
    depends_on: list[str]  # ["ingest"]
    artifacts: list[dict]  # [{filename, label, description, type: "image"|"data"}]
    fields: dict           # {field_name: {label, description, dtype: "int"|"float"}}
    aggregation: list      # [{type, source, target/prefix, ...}]  — see Aggregator section

    def needs_processing(self, sample_dir) -> bool: ...
    def filter_todo(self, entries, dataset_dir) -> list: ...
    def ensure_sample_dir(self, entry, dataset_dir) -> str: ...

    @abstractmethod
    def process(self, entries, dataset_dir, workers=32): ...
```

### Plugin File Requirements

Every processor is ONE .py file. Every file MUST have Fire CLI at the bottom:

```python
def main(entries_json, dataset_dir="datasets/pexels", workers=32):
    with open(entries_json) as f:
        entries = json.load(f)
    proc = MyProcessor()
    proc.process(entries, dataset_dir, workers)

if __name__ == "__main__":
    fire.Fire({"main": main})
```

GPU processors add subprocess-isolated Fire subcommands:

```python
def gpu_worker(list_path, gpu_id=0):
    ...  # CUDA work, exits after

if __name__ == "__main__":
    fire.Fire({"main": main, "gpu_worker": gpu_worker})
```

### Collision Safety

`discover_processors()` validates on load:
- No duplicate processor names
- No artifact filename collisions between processors
- No field name collisions between processors

Violations raise `ValueError` at import time.

## Processors

### compress (`preprocess/processors/compress.py`)

**Depends on**: nothing (root processor)
**Parallelization**: CPU Pool (ffmpeg subprocesses)

Compression ladder: single-decode multi-output ffmpeg cascade. Decodes each source video ONCE and produces up to 6 resolution proxies in a single ffmpeg invocation. Targets the SMALLER dimension (not always height); e.g., "480p" means smallest side ≤ 480px. Videos whose smaller dimension is already ≤ target are NOT upscaled. Uses H.264 veryfast preset CRF 28.

Produces per sample (6 files):
- `compress_1080p.mp4`, `compress_720p.mp4`, `compress_480p.mp4` (primary proxy), `compress_360p.mp4`, `compress_240p.mp4`, `compress_144p.mp4`

Fields: none

### ingest (`preprocess/processors/ingest.py`)

**Depends on**: `["compress"]` (needs proxy videos for fast decode)
**Parallelization**: CPU Pool with PyAV (thread_type='AUTO')

Uses `select_video_source()` to pick the best proxy (480p preferred, falls back through other resolutions, then original video.mp4). Opens each video ONCE via PyAV sequential decode. Collects all needed frame indices in one pass:
- Key frames: `[0, total//2, total-1]` → 3 thumbnails at 512px height
- Sprite frames: `np.linspace(0, total-1, 25)` → 5x5 grid at 192x108

Also extracts metadata from PyAV stream info + `os.path.getsize()` (from ORIGINAL source, not proxy).
Benchmarked: 3.3 vid/s at 16 workers on 96 CPU cores.

Produces per sample (5 files):
- `thumb_first.jpg` — 512px height, aspect-preserved, JPEG q=30
- `thumb_middle.jpg` — 512px height, primary display image
- `thumb_last.jpg` — 512px height
- `sprite.jpg` — 960x540, 5x5 grid, 25 frames at 192x108 contain-padded
- `metadata.json` — `{width, height, fps, num_frames, duration, file_size_mb}`

Fields (6): width, height, fps, num_frames, duration, file_size_mb

### clip (`preprocess/processors/clip.py`)

**Depends on**: `["ingest"]` (needs thumb_first/middle/last.jpg)
**Parallelization**: subprocess for CUDA isolation → torch.multiprocessing across all GPUs

Model: `openai/clip-vit-base-patch32` (ViT-B/32, 512-dim). Batched GPU inference via `_batched_clip_forward()` — FORWARD_BATCH=64 images per GPU forward pass. PREFETCH_CHUNK=32 samples (96 images) loaded in parallel via ThreadPoolExecutor before each GPU batch. Timestamped `[HH:MM:SS] GPU N:` logging every chunk (no tqdm — doesn't render in spawned processes).

Processes ONLY batch entries. Does NOT rebuild FAISS (that's the aggregator's job).

Produces per sample (4 files):
- `clip_embedding.npy` — float16 (512,), L2-normalized, from thumb_middle.jpg
- `clip_first.npy` — from thumb_first.jpg
- `clip_last.npy` — from thumb_last.jpg
- `clip_std.json` — `{clip_std: float}` mean pairwise cosine distance of the 3 embeddings

Fields (1): clip_std

### raft_flow (`preprocess/processors/raft_flow.py`)

**Depends on**: `["ingest"]` (needs sprite.jpg)
**Parallelization**: subprocess for CUDA isolation → torch.multiprocessing across all GPUs

Model: RAFT small (from CommonSource `libs/`). Reads sprite.jpg, splits into 25 frames, resizes to 256px, computes 24 consecutive flow pairs. Chunked processing (16 samples/chunk) with timestamped `[HH:MM:SS] GPU N:` logging.

Produces per sample (1 file):
- `flow_stats.json` — 5 numeric fields

Fields (5): flow_mean_magnitude, flow_max_magnitude, flow_min_magnitude, flow_std_magnitude, flow_temporal_std

### phash (`preprocess/processors/phash.py`)

**Depends on**: `["ingest"]` (needs sprite.jpg)
**Parallelization**: CPU Pool

Uses `imagehash.phash` (DCT-based, 64-bit hash). Reads sprite.jpg, splits 25 frames, 24 Hamming distances.

Produces per sample (1 file):
- `phash_stats.json` — 4 numeric fields

Fields (4): phash_mean_change, phash_max_change, phash_std_change, phash_temporal_std

## I/O and Parallelization Requirements

**NFS is slow. GPU utilization will suffer if data isn't prefetched.**

Every processor MUST address the I/O bottleneck. Loading files from network storage is the #1 bottleneck — not computation. If a GPU processor loads images synchronously, the GPU sits idle 90% of the time.

### Required Patterns

**CPU processors (ingest, phash)**: Use `multiprocessing.Pool(workers)`. Each worker handles one sample end-to-end (load → process → save). The pool IS the parallelism — workers run in parallel on different samples. No additional prefetching needed because the workers themselves overlap I/O.

**GPU processors (clip, raft_flow)**: MUST use a producer-consumer pattern:
1. **Producer thread(s)**: `ThreadPoolExecutor` loads images from NFS into RAM in the background
2. **Consumer (GPU)**: Processes the already-loaded batch while the next batch is being loaded
3. **Result**: GPU utilization stays near 100% because data is always ready

```python
# Required pattern for GPU processors:
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

def gpu_worker(gpu_id, sample_ids, dataset_dir):
    model = load_model(device=f"cuda:{gpu_id}")

    # Prefetch: load images in background threads while GPU works
    prefetch_pool = ThreadPoolExecutor(max_workers=8)

    for batch_start in range(0, len(sample_ids), BATCH_SIZE):
        batch_ids = sample_ids[batch_start:batch_start + BATCH_SIZE]

        # Submit image loads to thread pool (non-blocking)
        futures = [prefetch_pool.submit(load_image, sid) for sid in batch_ids]
        images = [f.result() for f in futures]  # blocks only if not ready yet

        # GPU forward pass (images already in RAM)
        embeddings = model(images)

        # Save results
        for sid, emb in zip(batch_ids, embeddings):
            np.save(os.path.join(sample_dir(...), "clip_embedding.npy"), emb)
```

**RAFT specifically**: Each video's sprite.jpg is ~60-150KB. Loading 500 sprites from NFS takes ~30s if serial but ~2s if 32 threads. The RAFT model loads ONCE per GPU worker, processes all assigned samples sequentially (but with prefetched data). With 8 GPUs processing ~63 samples each: RAFT forward passes take ~24 × 30ms = 0.7s per video, so 63 videos = ~45s of GPU time. Total with prefetch: ~50s. Without prefetch: ~5min+ (GPU idle waiting for NFS).

### Profiling Requirement

Every processor MUST be profiled after implementation. The profile must show:
- Per-sample time breakdown (I/O load, compute, save)
- GPU utilization percentage (for GPU processors)
- Throughput (samples/second)
- Comparison to theoretical maximum

If GPU utilization is below 80% for a GPU processor, the I/O prefetching is insufficient and must be improved before the processor is considered done.

### Testing

The `tests/` directory contains benchmarks and profiling scripts:
- `bench_pyav_ingest.py` — PyAV decode benchmarks
- `bench_gpu_decode.py`, `bench_gpu_subprocess.py` — GPU decode experiments
- `benchmark_ingest.py` — end-to-end ingest profiling
- `profile_ingest.py` — per-function profiling
- `compress_ladder.py` + `compress_ladder/` — compression ladder test cases
- `benchmark_results.json` — saved benchmark data

VLM verification on first batch: check that thumbnails and CLIP search results are visually correct.

### Dependency Graph

```
compress ──→ ingest ──→ clip
                    ──→ raft_flow
                    ──→ phash
```

## Pipeline CLI

```bash
bash process.sh --process=ingest,phash --batch_size=500             # compress auto-added as dep
bash process.sh --process=all --skip=clip,raft_flow --batch_size=500  # everything except GPU-heavy
bash process.sh --process=all --batch_size=500                      # all processors
bash process.sh --process=all --skip=raft_flow --batch_size=500     # all except raft_flow
bash process.sh --process=all --batch_size=500 --shuffle            # randomized (default True)
uv run python preprocess/aggregator.py --dataset_dir datasets/pexels  # standalone aggregation
```

**`--process` is required** — no silent "run everything" default. Use `--process=all` to run all processors. Valid flags: `--manifest`, `--dataset_dir`, `--batch_size`, `--workers`, `--shuffle`, `--process`, `--skip`, `--auto_aggregate`. Unknown flags are rejected.

### process_all.py Logic

All log lines timestamped via `_log()` helper (`[HH:MM:SS] message`).

1. `_validate_kwargs()` — reject unknown CLI flags (hard exit)
2. `discover_processors()` — scan processors/ folder
3. Require `--process` flag (or `--skip`). `--process=all` enables everything.
4. `_parse_name_list()` — validate comma-separated names against available processors
5. `resolve_dependencies()` — topological sort with transitive deps
6. `format_processor_help()` — shows available processors on error
7. Print full config immediately
8. Load manifest
9. Find work (any enabled processor has missing artifacts)
10. Shuffle if requested (`--shuffle`, default True)
11. **Prerequisite priority sorting** — `priority_sort()` + `count_satisfied_deps()` + `format_tier_breakdown()`. Stable-sort by # of processors whose deps are satisfied (descending).
12. Batch loop:
   - Per enabled processor in dependency order:
     - `filter_todo(batch)` — only samples missing THIS processor's files
     - `process(todo)` — ONLY those samples
   - Print timing + ETA
   - **Auto-aggregation** — run aggregator after each batch (`--auto_aggregate`, default True).
     Batch-scoped: passes the batch's sample list and active processor names directly to the
     aggregator, so it skips the expensive full filesystem scan and only aggregates rules from
     the processors you specified. E.g., `--process=clip` only aggregates CLIP vectors + clip_std,
     not phash/raft_flow/metadata. If you explicitly name a processor (even if it had no work to do
     in that batch), its aggregation rules still run.

### CRITICAL RULE

**Each processor processes ONLY the given entries.** No processor scans or processes videos outside the current batch. This is the fundamental architectural rule that makes the system fast and predictable.

## Aggregator (Plugin-Driven)

File: `preprocess/aggregator.py`

Called by `run.sh` before server start, by `process_all.py` after each batch (auto-aggregation), or standalone.

The aggregator reads aggregation rules from processor plugins — no hardcoded file paths.

### Aggregation Rule Types

Each processor declares an `aggregation` class attribute (list of dicts):

1. **`json_dict`** — merge per-sample JSON files into `{video_name: data}` dicts
   ```python
   {"type": "json_dict", "source": "metadata.json", "target": "video_metadata.json"}
   ```
   Multiple processors can target the same file (values merge per video).

2. **`vector_index`** — read per-sample `.npy` vectors, build FAISS `IndexFlatIP`
   ```python
   {"type": "vector_index", "source": "clip_embedding.npy", "prefix": "clip", "dim": 512}
   ```
   Generates `{prefix}_embeddings.npz`, `{prefix}_index.faiss`, `{prefix}_names.json`.
   Generic — any processor can declare an embedding that gets FAISS-indexed.

### Aggregator Logic

Two modes: **full scan** (standalone) and **batch** (auto-aggregation from pipeline).

**Full scan** (`aggregate(dataset_dir=...)` — no extra args):
1. Discover processors, collect aggregation rules from ALL processors
2. Scan `samples/` directory tree to find all sample dirs
3. Load `cache_manifest.json` — diff against scanned samples to find new ones
4. Aggregate new samples across all rules

**Batch mode** (`aggregate(dataset_dir=..., sample_list=..., only_processors=...)` — from pipeline):
1. Skip filesystem scan entirely — sample list provided by caller
2. Only collect aggregation rules from the specified processors
3. Aggregate only the batch's samples, only for the active rules
4. E.g., `--process=clip` → only clip_std.json + clip_embedding.npy aggregation

**Shared behavior** (both modes):
- `json_dict`: loads existing cache file, merges new data (dict update = natural dedup)
- `vector_index`: builds name→embedding map from existing + new. Overwrites duplicates
  (re-aggregating the same sample replaces its vector, no duplicates in FAISS index).
  Logs `N new, M updated (dedup)` when overwrites occur.
- Cache manifest (`cache_manifest.json`) tracks `samples_included` as a set union —
  grows across batches without duplicates.
- `--clear_cache` flag to force full rebuild (both modes)
- All saves atomic (temp + rename)

## Server

Reads from `cache/` only. Loads all data generically:
- JSON dicts (video_metadata.json, video_stats.json) discovered from cache_manifest.json
- Vector indices ({prefix}_index.faiss) discovered by scanning cache/ for `*_index.faiss` files

Serves thumbnails from `samples/` with transparent shard routing:

```
/thumbnails/<dataset>/<video_name>/<filename>
→ server computes shard internally
→ serves from datasets/<dataset>/samples/<shard>/<video_name>/<filename>
```

Frontend URLs are clean — no shard in the URL. Server handles the mapping.

### Hot-Reload

The server exposes `/api/reload/<dataset>` which re-reads all cache/ files without restarting the server process. The frontend polls `/api/status/<dataset>` and shows "Reload available" when data counts change.

### Server API Endpoints

| Endpoint | Method | Params | Description |
|----------|--------|--------|-------------|
| `/` | GET | — | Serve the web UI (Svelte SPA from `static/`) |
| `/api/datasets` | GET | — | List datasets with counts, available vector indices |
| `/api/search/fuzzy` | GET | `dataset`, `q`, `page`, `page_size`, `sort`, `sort_dir`, `thumb_filter`, `fav_filter`, `random_seed`, `min_*`/`max_*` | FZF extended-mode text search. Server-side sort+paginate. Also computes CLIP scores if available |
| `/api/search/clip` | GET | `dataset`, `q`, `index` (default "clip"), same pagination/filter params | Semantic search via FAISS. `index` selects which vector index to query |
| `/api/search/hull` | POST | Body: `{dataset, selected, index, page, page_size, sort, sort_dir, thumb_filter, fav_filter, random_seed, min_*/max_*}` | Convex hull (centroid) search from selected videos |
| `/api/metadata_stats/<dataset>` | GET | — | Min/max/count for all numeric fields (count = samples with that field) |
| `/api/histograms/<dataset>` | GET | `bins` (default 60) | Histogram bin counts for all numeric fields |
| `/api/field_info` | GET | — | Field descriptions + artifact metadata from all plugins |
| `/api/config` | GET | — | Shared constants (sprite grid dimensions) |
| `/api/status/<dataset>` | GET | — | Data counts for reload detection. Per-vector-index counts |
| `/api/reload/<dataset>` | GET | — | Hot-reload cache without restart |
| `/api/favorites/<dataset>` | GET | — | Returns `{favorites: [video_name, ...]}` |
| `/api/favorites/<dataset>` | POST | Body: `{video_name, action: "add"\|"remove"}` | Toggle favorite, persists to `user_data/favorites.json` |
| `/api/video_info/<dataset>/<video_name>` | GET | — | Full video details: metadata, stats, thumbnails, video URL |
| `/api/video/<dataset>/<video_name>` | GET | — | Stream original video file for playback |
| `/thumbnails/<dataset>/<video_name>/<file>` | GET | — | Serve per-sample file with transparent shard routing |

## Frontend

Svelte + Vite. Built to `static/`, served by Flask.

### v2 Simplifications (no backward compat)

- **No quality toggle** — one thumbnail resolution (512px), no "small vs HQ" concept
- **No fallback to small thumbnails** — if thumb_middle.jpg is missing, show error
- **Thumbnail URLs**: `/thumbnails/pexels/19012581/thumb_middle.jpg` (note: `thumb_` prefix)
- **No `hq_` prefix logic** — the prefix was a v1 concept, removed entirely
- **Settings panel**: stub exists (`SettingsPanel.svelte`) but not actively used. Can be extended for future settings.

### Field dtype: int vs float

Each processor field declares `dtype: "int"` or `"float"`. This propagates through `/api/field_info` to the frontend. Integer fields use step=1 (whole numbers only). Float fields scale step by range (0.001 for small ranges, 0.01 for medium, 0.1 for large). The `round()` function in HistogramFilter respects the step precision.

### Filter Enhancements

- **Sample count in header**: Each filter shows `label (count)` where count = number of samples that have a value for that field. Count comes from `/api/metadata_stats` (added `count` field).
- **Min/max handle swap**: When dragging the min handle past the max (or vice versa), the handles implicitly swap roles so the range always stays valid.
- **Ternary filters (TernaryFilter widget)**: Reusable 3-state button that cycles `Any → Only → None`. Used for:
  - **Thumbnail filter** (`thumb_filter`): Any = all videos, Only = videos with thumbnails, None = videos without thumbnails. Icons: `mdi:image-outline`, `mdi:image-check`, `mdi:image-off`.
  - **Favorites filter** (`fav_filter`): Any = all videos, Only = favorited videos, None = non-favorited. Icons: `mdi:heart-outline`, `mdi:heart`, `mdi:heart-off`.
  - Server-side filtering via `thumb_filter` and `fav_filter` query params (`any`|`only`|`none`).
  - URL state: `thumb=only|none` (omit when `any`), `fav=only|none` (omit when `any`).

### Favorites

Videos can be favorited (hearted). Favorites are stored server-side in `user_data/favorites.json` as `{dataset: [video_name, ...]}`. No user concept yet — single global file.

- **Heart on VideoCard**: Small heart icon in top-right of thumbnail. Appears on hover (opacity 0 → 1). Filled red when favorited, outline when not. Click toggles.
- **Heart on DetailPanel**: Toolbar row below the video with a "Favorite"/"Favorited" button. Scalable for future toolbar actions.
- **API**: `GET /api/favorites/<dataset>` returns list, `POST /api/favorites/<dataset>` with `{video_name, action: "add"|"remove"}` toggles.
- **Store**: `favorites` (Set), `favFilter` ('any'|'only'|'none') in stores.js.

### Sort Behavior

When sorting by a numeric field, videos that lack a value for that field are **excluded from results**. This prevents "undefined" values from cluttering the sorted view. Sorting by "name" or "random" includes all results.

### Server-Side Pagination

All sorting, filtering, and pagination is done server-side. The frontend sends `page`, `page_size`, `sort`, `sort_dir`, `thumb_filter`, `fav_filter`, `random_seed` to the API. The server returns `{results, total, page, page_size, result_histograms}`. The frontend's `currentResults` holds ONE page of results, `totalResults` holds the server-reported total. Page changes and sort changes trigger new API calls.

**Histograms**: `/api/histograms/<dataset>` computes full-dataset histograms on-the-fly (no pre-computed file). Search results also include `result_histograms` via `compute_result_histograms()` — histograms computed from filtered results. Both use stable axis ranges from `metadata_stats` min/max.

### Reload Indicator

Renders in the SearchHeader (between title and dataset selector). Polls `/api/status/<dataset>` every 30 seconds. When new data is detected (counts changed since page load), shows a pulsing refresh icon (`mdi:refresh`) with `active-toggle` style. Click reloads the page. Has a Popover tooltip explaining what it means.

**Critical**: `/api/status` must read **disk** (cache_manifest.json) each poll, NOT in-memory data. The server loads data once at startup — in-memory counts never change, so comparing against in-memory data always shows "up to date". The fix: status endpoint reads cache_manifest.json fresh from disk each request. When preprocessing adds samples and runs aggregation, the cache_manifest on disk updates, and the next poll detects the difference.

**Known issue (2026-02-28)**: Previously broken — status endpoint returned in-memory counts, so the indicator never triggered. Fixed by reading cache_manifest.json from disk.

### Frontend Components

Components in `frontend/src/components/`:
- `SearchHeader.svelte` — search bar, mode selector, reload indicator
- `VideoGrid.svelte` — paginated grid of video cards
- `VideoCard.svelte` — thumbnail + sprite hover + favorite heart
- `DetailPanel.svelte` — inline video detail with metadata, video playback
- `FilterPanel.svelte` — histogram filters + ternary filters
- `StatsPanel.svelte` — dataset statistics display
- `ExportModal.svelte` — copy selected video names
- `StatusBar.svelte` — bottom status bar
- `ReloadIndicator.svelte` — pulsing reload icon when new data available
- `SyntaxHelp.svelte` — search syntax reference
- `SettingsPanel.svelte` — stub for future settings

Widgets in `frontend/src/components/widgets/`:
- `HistogramFilter.svelte` — range slider with histogram visualization
- `TernaryFilter.svelte` — 3-state toggle (Any/Only/None)
- `Popover.svelte` — tooltip/popover component
- `SafeImage.svelte` — image with error handling

Libraries in `frontend/src/lib/`:
- `api.js` — API client functions
- `fields.js` — field metadata and descriptions
- `format.js` — formatting utilities
- `sort.js` — sort logic
- `stats.js` — statistics helpers
- `stores.js` — Svelte stores (all reactive state)
- `url.js` — URL state persistence

### Everything Else

All other frontend features carry forward unchanged:
- Search modes (fuzzy, CLIP, hull)
- Sort by any field + direction toggle + random
- Histogram filters with handles, log/linear Y, hover indicator
- Pagination
- Detail panel (inline, resizable)
- Sprite hover with progress bar
- Search highlighting
- URL state persistence
- Popovers for field descriptions
- Iconify icons

## File Structure

```
/root/CleanCode/Dumps/Searchable_Pexels_v2/
├── claude_instructions.md    # this manifest
├── concerns.md               # progress log, issues, findings
├── README.md                 # user-facing documentation
├── pyproject.toml
├── uv.lock
├── setup.sh
├── run.sh                    # build frontend + aggregate + start server
├── process.sh                # uv run python preprocess/process_all.py "$@"
├── .gitignore
├── metadatas.json            # raw Pexels metadata (input for distill_metadata.py)
├── preprocess/
│   ├── process_all.py        # discover, resolve deps, batch loop, timestamped logging
│   ├── aggregator.py         # build cache/ from samples/ (full scan or batch mode)
│   ├── distill_metadata.py   # raw JSON → manifest.json
│   ├── video_utils.py        # sample_shard, sample_dir, frame helpers, pure functions
│   └── processors/
│       ├── __init__.py       # discover_processors(), resolve_dependencies(), collect_aggregation_rules()
│       ├── base.py           # Processor base class (ensure_sample_dir: hardlink + symlink fallback)
│       ├── compress.py       # compression ladder (root processor, ffmpeg)
│       ├── ingest.py         # thumbnails + sprites + metadata (PyAV, depends on compress)
│       ├── clip.py           # CLIP embeddings (subprocess, batched GPU inference)
│       ├── raft_flow.py      # RAFT optical flow (subprocess, all GPUs)
│       └── phash.py          # perceptual hash (CPU Pool)
├── server/
│   ├── app.py                # Flask server, all API endpoints
│   ├── search.py             # search logic (fuzzy, CLIP, hull)
│   └── clip_encoder.py       # CLIP text encoding for queries
├── frontend/
│   └── src/                  # Svelte app (see Frontend Components section)
├── static/                   # vite build output (gitignored)
├── libs/CommonSource/        # RAFT wrapper (gitignored)
├── tests/                    # benchmarks and profiling scripts
├── datasets/pexels/          # data (gitignored except manifest)
├── user_data/                # favorites.json (gitignored)
└── .venv/                    # uv venv (gitignored)
```

## Auto-Discovery Code (`preprocess/processors/__init__.py`)

```python
import os, importlib
from .base import Processor

def discover_processors():
    """Scan processors/ directory, import all modules, return {name: processor_instance}.

    Adding a new processor = dropping a .py file in the directory.
    No registration, no modification of any other file.
    """
    processors = {}
    pkg_dir = os.path.dirname(__file__)
    for filename in sorted(os.listdir(pkg_dir)):
        if filename.endswith('.py') and filename not in ('__init__.py', 'base.py'):
            module_name = filename[:-3]
            mod = importlib.import_module(f'.{module_name}', package='preprocess.processors')
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (isinstance(attr, type) and issubclass(attr, Processor)
                    and attr is not Processor and hasattr(attr, 'name')):
                    instance = attr()
                    processors[instance.name] = instance
    return processors

def resolve_dependencies(enabled_names, all_processors):
    """Given enabled processor names, add all transitive dependencies.
    Returns list in topological order (dependencies first).

    Example: resolve_dependencies({"clip"}, all_procs) → ["ingest", "clip"]
    """
    resolved = []
    visited = set()

    def visit(name):
        if name in visited:
            return
        visited.add(name)
        proc = all_processors[name]
        for dep in proc.depends_on:
            if dep not in all_processors:
                raise ValueError(f"Processor '{name}' depends on unknown processor '{dep}'")
            visit(dep)
        resolved.append(name)

    for name in enabled_names:
        visit(name)
    return resolved
```

## Base Class Code (`preprocess/processors/base.py`)

```python
class Processor:
    name: str              # "ingest", "clip", "raft_flow", "phash"
    human_name: str        # "Ingest", "CLIP Embeddings"
    depends_on: list[str]  # ["ingest"]

    artifacts: list[dict]  # [{filename, label, description, type}]
    fields: dict           # {field_name: {label, description, dtype: "int"|"float"}}

    def needs_processing(self, sample_dir):
        """True if any artifact file missing."""
        for a in self.artifacts:
            if not os.path.exists(os.path.join(sample_dir, a["filename"])):
                return True
        return False

    def filter_todo(self, entries, dataset_dir):
        """Return only entries needing this processor's work."""
        todo = []
        for entry in entries:
            sd = sample_dir(dataset_dir, entry["video_name"])
            if self.needs_processing(sd):
                todo.append(entry)
        return todo

    def ensure_sample_dir(self, entry, dataset_dir):
        """Create dir + origins.json + video.mp4 link. Return path."""
        sd = sample_dir(dataset_dir, entry["video_name"])
        os.makedirs(sd, exist_ok=True)

        origins_path = os.path.join(sd, "origins.json")
        if not os.path.exists(origins_path):
            with open(origins_path, "w") as f:
                json.dump({
                    "video_name": entry["video_name"],
                    "caption": entry.get("caption", ""),
                    "source_path": entry["source_path"],
                    "dataset": os.path.basename(dataset_dir),
                }, f)

        link_path = os.path.join(sd, "video.mp4")
        if not os.path.exists(link_path) and os.path.exists(entry["source_path"]):
            try:
                os.link(entry["source_path"], link_path)      # hardlink (same filesystem)
            except OSError:
                os.symlink(os.path.abspath(entry["source_path"]), link_path)  # fallback
        return sd

    def process(self, entries, dataset_dir, workers=32):
        """SUBCLASS IMPLEMENTS. Process ONLY given entries."""
        raise NotImplementedError
```

## Ingest Processor: How It Works

The ingest processor picks the best proxy via `select_video_source()` (prefers 480p, falls back through resolutions, then original). Opens each video ONCE via PyAV with `thread_type='AUTO'`. Sequential decode with frame skipping — only keeps frames at target indices.

```python
# Pseudocode for one video in the ingest processor:
import av

def process_one_video(entry, dataset_dir):
    sd = ensure_sample_dir(entry, dataset_dir)
    video_path, source_label = select_video_source(sd)  # 480p proxy preferred

    # Open via PyAV, sequential decode
    container = av.open(video_path)
    stream = container.streams.video[0]
    stream.thread_type = 'AUTO'
    total = stream.frames
    fps = float(stream.average_rate)
    h, w = stream.height, stream.width

    # Collect ALL needed indices, decode ONCE
    key_indices = {0, total // 2, max(0, total - 1)}
    sprite_indices = set(np.linspace(0, total - 1, 25, dtype=int))
    all_indices = sorted(key_indices | sprite_indices)

    # Sequential decode, skip unwanted frames
    frames = {}
    for i, frame in enumerate(container.decode(stream)):
        if i in all_indices:
            frames[i] = frame.to_ndarray(format='rgb24')  # (H, W, 3) uint8

    # Save thumbnails (512px height via resize_by_height_cv2, JPEG q=30)
    for name, idx in [("first", 0), ("middle", total//2), ("last", total-1)]:
        small = resize_by_height_cv2(frames[idx], 512)
        save_jpeg(small, os.path.join(sd, f"thumb_{name}.jpg"), quality=30)

    # Save sprite sheet (5x5 grid, 192x108 contain-padded via compose_sprite_cv2)
    sprite = compose_sprite_cv2(sprite_frame_list, 5, 5, 192, 108)
    save_jpeg(sprite, os.path.join(sd, "sprite.jpg"), quality=80)

    # Metadata from ORIGINAL source (not proxy)
    metadata = {
        "width": int(w), "height": int(h),
        "fps": round(float(fps), 3),
        "num_frames": total,
        "duration": round(total / max(fps, 1e-6), 3),
        "file_size_mb": round(os.path.getsize(entry["source_path"]) / (1024*1024), 2),
    }
    save_json(metadata, os.path.join(sd, "metadata.json"))
```

The `process()` method wraps this in `multiprocessing.Pool(workers)` with `tqdm`.

## Aggregator: How It Works

```python
# Pseudocode for preprocess/aggregator.py

def aggregate(dataset_dir, clear_cache=False, sample_list=None, only_processors=None):
    """
    Two modes:
      Full scan:  aggregate(dataset_dir)                    — scans all samples/, all rules
      Batch mode: aggregate(dataset_dir, sample_list=...,   — skips scan, scoped rules
                            only_processors=["clip"])
    """
    cache_dir = f"{dataset_dir}/cache"
    prev = load_json(f"{cache_dir}/cache_manifest.json")
    prev_names = set(prev.get("samples_included", []))

    if sample_list is not None:
        # Batch mode: caller provides samples directly, no filesystem scan
        new_samples = sample_list
        all_sids = sorted(prev_names | {sid for sid, _ in sample_list})
    else:
        # Full scan: walk samples/ directory tree
        all_samples = discover_sample_dirs(f"{dataset_dir}/samples")
        new_samples = [(sid, path) for sid, path in all_samples if sid not in prev_names]
        all_sids = [sid for sid, _ in all_samples]

    # Scope aggregation rules to active processors only
    processors = discover_processors()
    if only_processors is not None:
        processors = {k: v for k, v in processors.items() if k in only_processors}
    json_rules, vector_rules = collect_aggregation_rules(processors)

    # json_dict: merge into existing (dict update = natural dedup)
    for target, sources in json_rules.items():
        existing = load_json(f"{cache_dir}/{target}")
        for sid, path in new_samples:
            vname = video_name_from_sample_id(sid)
            existing.setdefault(vname, {}).update(read_sample_json(path, source))
        save(existing)

    # vector_index: name→emb map (overwrites = dedup, no duplicate rows)
    for rule in vector_rules:
        name_to_emb = {name: emb for name, emb in zip(existing_names, existing_embs)}
        for sid, path in new_samples:
            name_to_emb[video_name_from_sample_id(sid)] = np.load(path / source)
        # sorted keys → parallel arrays → FAISS IndexFlatIP
        save(name_to_emb)

    save_manifest({"samples_included": all_sids, ...})
```

## process_all.py: Full Logic

```python
VALID_ARGS = {"manifest", "dataset_dir", "batch_size", "workers", "shuffle",
              "process", "skip", "auto_aggregate"}

def process_all(manifest="datasets/pexels/manifest.json",
                dataset_dir="datasets/pexels",
                batch_size=500, workers=32, shuffle=True,
                process=None, skip=None, auto_aggregate=True, **kwargs):

    # 0. Reject unknown CLI flags
    _validate_kwargs(kwargs, VALID_ARGS, "process_all.py")

    # 1. Discover processors
    all_processors = discover_processors()

    # 2. Require --process (no silent "run everything" default)
    if process is None and skip is None:
        print(format_processor_help(all_processors))
        sys.exit(1)

    # 3. Determine enabled set
    if process == "all":
        enabled = set(all_processors.keys())
    else:
        enabled = set(_parse_name_list(process, ...))
    if skip:
        enabled -= set(_parse_name_list(skip, ...))

    # 4. Resolve dependencies (topological order)
    ordered = resolve_dependencies(enabled, all_processors)

    # 5. Print full config
    _log(f"processors: {ordered}")  # timestamped

    # 6. Load manifest
    entries = json.load(open(manifest))

    # 7. Find work
    todo = [e for e in entries if any(
        all_processors[p].needs_processing(sample_dir(dataset_dir, e["video_name"]))
        for p in ordered
    )]

    # 8. Shuffle + prerequisite priority sort
    if shuffle:
        random.shuffle(todo)
    todo, tier_counts = priority_sort(todo, dataset_dir, ordered, all_processors)
    print(format_tier_breakdown(tier_counts, len(ordered)))

    # 9. Batch loop
    for batch in batches(todo, batch_size):
        for proc_name in ordered:
            proc = all_processors[proc_name]
            batch_todo = proc.filter_todo(batch, dataset_dir)
            if not batch_todo:
                _log(f"  {proc.human_name}: all done")
                continue
            _log(f"  {proc.human_name}: {len(batch_todo)}/{len(batch)}...")
            proc.process(batch_todo, dataset_dir, workers)
        _log(f"Batch complete | Elapsed: ... | ETA: ...")

        # 10. Auto-aggregate (batch-scoped, fast)
        if auto_aggregate:
            batch_samples = [(sample_id(dataset, e["video_name"]),
                              sample_dir(dataset_dir, e["video_name"])) for e in batch]
            aggregate(dataset_dir=dataset_dir, sample_list=batch_samples,
                      only_processors=ordered)
```

## Server: Thumbnail Routing

The server computes the shard internally so the frontend never needs to know about it:

```python
@app.route("/thumbnails/<dataset>/<video_name>/<path:filename>")
def serve_thumbnail(dataset, video_name, filename):
    sd = sample_dir(os.path.join("datasets", dataset), video_name)
    return send_from_directory(sd, filename)
```

Frontend URL: `/thumbnails/pexels/19012581/thumb_middle.jpg`
Server resolves: `datasets/pexels/samples/ae/d3/19012581/thumb_middle.jpg`

No shard in the URL. Transparent to the frontend.

## run.sh

```bash
#!/bin/bash
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

# Build frontend
if [ -d "frontend" ]; then
    echo "Building frontend..."
    cd frontend
    [ -d "node_modules" ] || npm install
    npm run build
    cd "$REPO_ROOT"
fi

# Aggregate (build/update cache from samples — incremental, skips seen samples)
echo "Aggregating cache..."
uv run python preprocess/aggregator.py --dataset_dir datasets/pexels

# Start server
uv run python server/app.py --port "${1:-8899}"
```

## process.sh

```bash
#!/bin/bash
# Process videos. Passes all arguments to process_all.py.
#
# Usage:
#   bash process.sh --process=all                                # all processors
#   bash process.sh --process=clip --batch_size=500              # clip + deps only
#   bash process.sh --process=all --skip=raft_flow               # all except raft
#   bash process.sh --process=ingest,phash --batch_size=500      # specific processors
#   bash process.sh --process=all --auto_aggregate=False         # skip aggregation

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"
uv run python preprocess/process_all.py "$@"
```

## Speed Expectations

| Step | v1 (500 samples) | v2 (500 samples) | Why |
|------|-------------------|-------------------|-----|
| Ingest (thumbs+sprites+metadata) | ~10min (3 video opens) | ~5min (1 video open) | Single PyAV open per video, 480p proxy |
| CLIP | **15min (all 27K+)** | **~30s (500 only)** | Only processes batch |
| RAFT Flow | ~7min | ~7min | Same (subprocess, all GPUs) |
| PHash | ~10s | ~10s | Same (CPU Pool) |
| **Total per batch** | **~33min** | **~13min** | **60% faster** |
| **Total for 81K (162 batches)** | **~89 hours** | **~35 hours** | |

The biggest win is CLIP going from 15min to 30s per batch. The second win is ingest combining three video opens into one.

## Migration Steps

1. Create worktree at `/root/CleanCode/Dumps/Searchable_Pexels_v2/` on branch `processor-redesign`
2. Copy `datasets/pexels/manifest.json` from v1 (81MB, needed as input)
3. Symlink `metadatas.json` from v1 (only needed if re-distilling manifest)
4. `git clone` CommonSource into `libs/`
5. `uv sync` to create venv with all deps
6. `npm install` in `frontend/`
7. Implement all processor modules
8. Implement aggregator
9. Update server paths
10. Update frontend (remove quality toggle, update thumbnail URLs to `thumb_` prefix)
11. Delete old preprocessing scripts
12. Test: `bash process.sh --batch_size=10` — verify 10 samples fully processed
13. Test: `bash run.sh` — verify aggregation + server + UI
14. Profile: compare batch time to v1

**DO NOT copy thumbnails/, embeddings/, or any generated data from v1.** Everything must be regenerated from scratch to prove the system works end-to-end.

## Multi-Machine Safety

- Per-sample artifacts are individual files in isolated directories — safe for concurrent writes
- The `--shuffle` flag (default True) randomizes processing order so two machines process different samples
- No shared mutable state between machines during processing
- Aggregation: batch-scoped auto-aggregation after each batch, or standalone via `uv run python preprocess/aggregator.py`
- Atomic JSON writes (temp file + rename + .backup) for any aggregated files

## Constraints

- All Python via `uv run` — no pip, no conda, no system python
- Relative paths only (dump portability) except `/models/` for base models
- No silent errors — fail loudly. No try/except to paper over ignorance.
- PyAV for video decoding (benchmarked faster than decord2 — 3.3 vid/s vs 1.8 vid/s)
- All GPU steps (CLIP, RAFT) run as subprocesses for CUDA isolation
- GPU processors use timestamped `[HH:MM:SS] GPU N:` logging (tqdm doesn't render in spawned processes)
- `--process` flag required in process_all.py — no silent "run everything" default
- Every processor's parallelization strategy must be documented
- No backward compatibility with v1 data formats — clean break
- Per-sample files eliminate multi-machine race conditions
- Atomic JSON writes (temp + rename + backup) for any file that could be written by multiple processes

## Lessons Learned

- **PyAV > decord2 for ingest**: Benchmarked 3.3 vid/s (PyAV) vs 1.8 vid/s (decord2+PIL). decord2 PyPI wheel is CPU-only; building from source with CUDA explored but not viable.
- **GPU decode not viable**: PyNvVideoCodec crashes with FPE after ~4 videos sequentially; can't pickle across multiprocessing. CUDA 11.8 limitation. CPU decode is the ceiling.
- **NFS is the bottleneck, not decode**: Per-request latency on network storage dominates. 64 workers was initially used in v1; 16-32 is the sweet spot for v2.
- **CLIP `get_image_features()` breaks in newer transformers**: Returns `BaseModelOutputWithPooling`, not a tensor. Use `model.vision_model()` + `model.visual_projection()` explicitly.
- **tqdm doesn't render in spawned processes**: `torch.multiprocessing` with `spawn` method creates processes where tqdm position-based rendering fails. Use timestamped print statements instead.
- **Batched GPU inference matters**: CLIP with 1 image per forward pass = 0% utilization. FORWARD_BATCH=64 keeps GPUs busy.
- **BATCH_SIZE > samples/GPU = no progress**: With BATCH_SIZE=256 and 63 samples per GPU, tqdm shows 0% → 100% with nothing in between. Use PREFETCH_CHUNK for granular progress.
- **`/api/status` must read disk**: In-memory counts never change after server boot. Status endpoint reads `cache_manifest.json` fresh from disk each poll.
- **Auto-aggregation must be batch-scoped**: Full filesystem scan of samples/ after every 500-sample batch is O(minutes). Pass sample list directly → O(seconds).

## Terminology

- **Field**: named numeric value per video (e.g., `duration`, `clip_std`, `flow_mean_magnitude`). Comes from processor `fields` dicts. The unit of sort/filter/display in the frontend.
- **Artifact**: file produced by a processor in a sample directory. Two types: image (viewable in UI), data (JSON/numpy).
- **Processor**: Python module in `preprocess/processors/` that subclasses `Processor`. Auto-discovered by scanning the directory.
- **Sample**: one video and all its artifacts, living in `samples/<shard_level1>/<shard_level2>/<video_name>/`.
- **Cache**: aggregated data in `cache/`, derived from samples, fully regenerable by the aggregator.
- **Shard**: two-level directory prefix from sha256 hash of sample_id (not video_name). First 2 hex chars / next 2 hex chars (e.g., `ae/d3/`). Creates 65,536 possible buckets for scalability to 10M+ samples.
- **Ingest**: depends on compress. Opens the best proxy video once via PyAV and extracts all frame-based artifacts (thumbnails, sprite sheet) plus metadata. All downstream processors work on these extracted files, never touching the raw video again.
- **Aggregator**: the script that reads per-sample files and combines them into cache-level aggregated files (FAISS index, merged JSON). Runs incrementally — skips samples already in the cache manifest.
