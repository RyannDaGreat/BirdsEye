# BirdsEye — Project Manifest (v2: Processor Architecture)

## Glossary

| Term | Definition |
|------|-----------|
| **Dataset** | A named collection of videos (e.g., `pexels`). Lives under `datasets/<name>/`. Contains manifest, samples, and cache. |
| **Manifest** | `manifest.json` at dataset root. Array of `{video_name, caption, source_path}`. Source of truth for what videos exist. |
| **Sample** | One video and all its per-video artifacts, stored in `samples/<shard1>/<shard2>/<sample_id>/`. Self-contained unit of processing. |
| **Sample ID** | `<dataset>_<video_name>` (e.g., `pexels_19012581`). Used for shard hashing. |
| **Shard** | Two-level hex directory prefix from sha256 of sample_id. First 2 chars / next 2 chars (e.g., `ae/d3/`). Creates up to 65,536 buckets. |
| **Bucket** | A shard2-level directory (`samples/<s1>/<s2>/`) containing sample dirs. One of 65,536 possible locations. |
| **Artifact** | A file produced by a processor in a sample directory. Types: image (viewable in UI), data (JSON/numpy). |
| **Field** | A named per-video value (numeric or string). Declared by processors or intrinsic to the dataset. Sortable. The unit of sort/filter/display in the frontend. Subtypes: **Numeric Field** (e.g., `duration`, `clip_std`) — filterable by range, histogrammable, scatterplottable, shown in numeric field bars. **String Field** (e.g., `caption`, `video_name`) — searchable and sortable alphabetically but not range-filterable. |
| **Processor** | A Python module in `preprocess/processors/` subclassing `Processor`. Auto-discovered. Produces artifacts and declares fields. |
| **Cache** | `datasets/<name>/cache/`. Aggregated data derived from samples: merged JSON dicts, FAISS indices. Fully regenerable by the aggregator. |
| **Cache Manifest** | `cache/cache_manifest.json`. Tracks which samples have been aggregated, timestamps, counts. |
| **Aggregator** | `preprocess/aggregator.py`. Reads per-sample files and combines them into cache. Incremental or full-scan. |
| **Dirty** | A `.dirty` marker file indicating unaggregated artifacts. Exists at sample, bucket, and shard levels. (TODO — not yet implemented.) |
| **Proxy** | A 480p transcoded copy of the original video (`video_480p.mp4`). Created by the compress processor. Downstream processors prefer it for faster decode. |
| **Origins** | `origins.json` in each sample dir. Records video_name, caption, source_path, dataset. Created by `ensure_sample_dir()`. |
| **Sprite** | A 5×5 grid of 25 evenly-spaced frames from a video, saved as `sprite.jpg`. Used for hover scrubbing in the UI. |
| **Thumbnail** | `thumb_first.jpg`, `thumb_middle.jpg`, `thumb_last.jpg`. 512px height JPEGs of first/middle/last frames. |
| **Embedding** | A CLIP vector (512-dim float16) per video. Stored per-sample as `.npy`, aggregated into FAISS index. |
| **Vector Index** | A FAISS `IndexFlatIP` plus parallel `_names.json` and `_embeddings.npz`. Enables cosine similarity search. |
| **Batch** | A chunk of entries processed together by the pipeline (default 500). Auto-aggregation runs after each batch. |
| **Pipeline** | `process_all.py`. Discovers processors, resolves dependencies, processes in topological order, batch loop. |
| **Ingest** | The processor that opens the best proxy video once via PyAV and extracts all frame-based artifacts (thumbnails, sprite sheet) plus metadata. Depends on compress. All downstream processors work on these extracted files, never touching the raw video again. |
| **Enriched** | A search result with `metadata` and `stats` dicts attached by the server before returning to frontend. |
| **Hull** | Convex hull search. Finds videos nearest to the centroid of selected videos' embeddings. |
| **Field Bar** | A UI chip showing a numeric field label (dim) and value (accent). Shared component (`FieldBar.svelte`) used in both stats panel and detail panel. Two parts: label (gray, left) and value (blue/accent, right). Only displays numeric fields. In the stats panel, field bars are toggleable (click to include/exclude from scattergram) — toggleable bars show a small icon (`mdi:check` in accent / `mdi:close` in dim) on the left and `title="Click to toggle"`. Values are right-aligned (`margin-left: auto`), bars width: `max-content` (widest bar, not full column). Active border is 40% opacity accent (not solid). Has `highlighted` prop for cross-component hover highlighting. In the stats panel, field bar tooltips follow the mouse (using `.mouse-tip` class) instead of Popover, because Popover blocks the view of adjacent fields. |
| **Ternary Filter** | A 3-state UI toggle cycling Any → Only → None. Used for thumbnail and favorites filtering. |
| **Caption** | AI-generated text description of a video from the raw Pexels metadata. |
| **FZF** | Fuzzy finder syntax used for text search. Space=AND, `\|`=OR, `!`=NOT, `'quoted'`=exact phrase. |
| **Search Area** | The main tile grid (`VideoGrid.svelte`) where search results are displayed. Shows video cards in an auto-fill grid. In empty/error states, shows a centered message + BirdsEye logo watermark at 2/3 width, 8% opacity, matching text color. |
| **Dynamic (modifier)** | A field modifier meaning "computed on-the-fly, not stored on disk." Orthogonal to the numeric/string axis — you can have a dynamic numeric field (e.g., CLIP Score) or a dynamic string field (future). Dynamic fields are ephemeral: they change when the query or context changes. In the sort dropdown, dynamic fields are visually distinguished with a marker prefix (via `dynamicFieldLabel()` pure function). Future: user-defined dynamic fields via an expression editor. |
| **Scatterplot Matrix** | (abbrev. SPLOM) An N×N grid of pairwise scatter plots for all toggled numeric fields. Diagonal cells show per-field histograms, off-diagonal cells show scatter plots of field[row] vs field[col]. Canvas-rendered for performance with alpha-crop: `findAlphaBounds(canvas, dpr)` pure function in `canvas.js` scans for non-zero alpha pixels to compute a tight bounding box, eliminating wasted space from generous label padding (PAD_LEFT/RIGHT/TOP=150). Mouse coordinates transform through crop offset for hover detection. Lives in the statistics panel. Standard statistical visualization for exploring correlations between multiple variables at a glance. Hovering a cell sets both row and column field keys in `hoveredFields` for cross-component highlighting. |
| **Preview Button Bar** | Toolbar row above the video in the detail panel. Houses the favorite toggle and future action buttons. Not collapsible (always visible when panel is open). |
| **Data Source Selector** | Two-row mode tab selector in the statistics panel. Top row (mandatory): Results / Dataset / Selection. Bottom row (optional): Results / Dataset / Selection / None. When bottom ≠ None, all statistics show differential (top minus bottom). |
| **Quantized Transfer** | Compact data encoding for large numeric arrays. Field values are normalized to 0–255 (uint8) using known min/max from `metadata_stats`, sent as JSON arrays, gzipped. Frontend reconstructs real values: `value = min + (q / 255) * (max - min)`. Used for scattergram dataset-level sampling. |
| **Cross-Component Field Highlighting** | `hoveredFields` store (Set of field keys) syncs highlighting across stats field bars, filter histograms, and SPLOM. Hovering any field anywhere highlights it everywhere: field bar gets `.highlighted` class, histogram gets accent outline, SPLOM highlights row/column. SPLOM cell hover sets both row and column field keys in `hoveredFields`. |

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!!! HIGH PRIORITY: THEORY OF MIND IN ALL USER-FACING TEXT                      !!!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

**Every error message, tooltip, label, and hint must be written for a newcomer who
has never seen this codebase.** This is the psychological principle of Theory of Mind:
the ability to understand that other people don't share your knowledge.

- **No internal jargon in user-facing text.** Don't say "vector index" or "embedding
  index" — say what it means: "image similarity search" or "CLIP embeddings".
- **Be specific, not generic.** If we know the dataset name, the missing processor,
  and the available alternatives — say all of that. Don't say "may not have been
  processed" when we know it wasn't. Don't say "try again later" when we know exactly
  what's wrong.
- **Every error gets two parts:** (1) a concise technical error (for developers), and
  (2) a layman's hint explaining what it means and what to do about it, using the
  specific context (dataset name, search mode, what's available vs. what's missing).
- **Dynamic, not canned.** Error hints should interpolate real values — the actual
  dataset name, the actual missing/available features. Not boilerplate.

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!!! NON-NEGOTIABLE: YOU MUST USE CONCERNS.MD                                   !!!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

**`concerns.md` is append-only. It is this project's historical record of HOW the software
came to be — including every mistake, wrong turn, and lesson learned along the way.**

- **Every mistake, bug, failed approach, and lesson learned MUST go into concerns.md** with timestamps.
  This is how we learn from our mistakes. If it's not in concerns.md, we'll repeat it.
- **When removing resolved items from the manifest**, dump the history into concerns.md first.
  The manifest stays clean and current; concerns.md keeps the full record.
- **concerns.md is NEVER trimmed or cleaned up.** It grows forever. That's the point.
- **Motivation**: A future Claude session (or human) should be able to read concerns.md and
  understand every wrong turn, every failed experiment, every architectural decision that was
  reversed — and WHY. This prevents repeating mistakes across sessions.

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
- **Separators must touch edges.** Lines/separators must touch adjacent borders with no gaps. Dotted separator in analysis column uses negative margins to extend past column padding.
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
4. **Export** — copy or download video names as newline-separated text. "Export All" must export ALL matching results from the current search (not just the visible page). "Export Selected" exports only manually selected videos. Both modes support copy-to-clipboard and download-as-file (`.txt`, browser save-as dialog, floppy disk icon `mdi:content-save`).
5. **Filterable by any numeric field** — histogram range selectors with draggable handles
6. **Sortable by any field** — ascending/descending toggle, random shuffle. Dynamic fields (computed on-the-fly, like CLIP Score) appear in the sort dropdown with a marker prefix via `dynamicFieldLabel()`. Currently the only dynamic field is CLIP Score (cosine similarity of query text vs stored CLIP embedding, computed server-side in all search modes when sorting by score).
7. **Pluggable processing** — add new analyses by dropping a Python file
8. **Statistics panel** — three side-by-side resizable columns: Analysis (left), Scatterplot Matrix (center), Word Frequency (right). Draggable vertical split handles between columns (default: equal thirds via `flex: 1`; drag switches to fixed pixel width). Analysis column has a non-scrolling header (Analysis label, DataSourceSelector, dotted separator, Fields header with All/None buttons) and a scrollable field list. Each column has its own Log/Lin toggle button inline with the section label header. Data source selector chooses what population to analyze (Results, Dataset, Selection) with optional differential (A minus B). Scattergram uses sampled + quantized data transfer for dataset-level views.

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
- **Store**: `hoveredFields` (Set of field keys) in stores.js — cross-component field highlighting sync.

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
- `StatsPanel.svelte` — dataset statistics display (three resizable columns)
- `ExportModal.svelte` — copy selected video names
- `StatusBar.svelte` — bottom status bar
- `ReloadIndicator.svelte` — pulsing reload icon when new data available
- `SyntaxHelp.svelte` — search syntax reference
- `SettingsPanel.svelte` — stub for future settings

Stats subcomponents in `frontend/src/components/stats/`:
- `ScatterplotMatrix.svelte` — SPLOM with canvas caching + alpha-crop
- `WordFrequency.svelte` — CSS vertical bar chart with selectable text labels
- `DataSourceSelector.svelte` — two-row data source selector with help popover

Widgets in `frontend/src/components/widgets/`:
- `HistogramFilter.svelte` — range slider with histogram visualization
- `TernaryFilter.svelte` — 3-state toggle (Any/Only/None)
- `Popover.svelte` — tooltip/popover component
- `SafeImage.svelte` — image with error handling
- `ModeTabRow.svelte` — reusable mode tab row (shared by search header, data source selector)
- `FieldBar.svelte` — field chip with checkbox icons, highlighted prop, mouse event forwarding

Libraries in `frontend/src/lib/`:
- `api.js` — API client functions
- `canvas.js` — canvas rendering utilities: `drawScatter`, `drawHistogram`, `findAlphaBounds`
- `fields.js` — field metadata, descriptions, `FIELD_ORDER`, `sortFieldKeys()`
- `format.js` — formatting utilities
- `sort.js` — sort logic
- `stats.js` — statistics helpers
- `stores.js` — Svelte stores (all reactive state)
- `url.js` — URL state persistence

### CSS Shared Classes

In `frontend/src/app.css`:
- `.separator` and `.separator.dotted` — horizontal separators. Dotted separator uses negative margins to extend past column padding so it touches edges.
- `.mouse-tip` — shared mouse-following tooltip class (used by field bars in stats panel instead of Popover).
- `::-webkit-scrollbar` height set to `var(--space-md)` for horizontal scrollbar sizing.

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
│       ├── __init__.py       # discover_processors(), resolve_dependencies(), collect_text_encoders()
│       ├── base.py           # Processor base class (embedding_space, encode_text, ensure_sample_dir)
│       ├── compress.py       # compression ladder (root processor, ffmpeg)
│       ├── ingest.py         # thumbnails + sprites + metadata (PyAV, depends on compress)
│       ├── clip.py           # CLIP embeddings (subprocess, batched GPU inference)
│       ├── raft_flow.py      # RAFT optical flow (subprocess, all GPUs)
│       └── phash.py          # perceptual hash (CPU Pool)
├── server/
│   ├── app.py                # Flask server, all API endpoints
│   └── search.py             # search logic (fuzzy, CLIP, hull)
├── frontend/
│   └── src/                  # Svelte app (see Frontend Components section)
├── static/                   # vite build output (gitignored)
├── libs/CommonSource/        # git submodule — RAFT wrapper, shared ML utilities
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
    Detects circular dependencies and raises ValueError with the cycle path.

    Example: resolve_dependencies({"clip"}, all_procs) → ["ingest", "clip"]
    """
    resolved = []
    visited = set()
    in_progress = set()  # cycle detection

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

Thin bash bootstrapper — only does what must be bash (uv install, lockfile), then
delegates to Python:

```bash
bash run.sh [--port PORT] [--skip_aggregate]
bash run.sh -- --help
```

**Architecture decision**: Argument parsing, dependency installation, frontend build,
aggregation, and server startup all live in Python (`server/app.py` Fire CLI). This
gives us typed arguments, auto-generated `--help`, and proper validation for free.
Bash was error-prone — unknown args like `--google` were silently accepted as port values.

**Two Fire subcommands:**
- `startup` — full sequence: build frontend → aggregate → start server (default via run.sh)
- `serve` — just start the server (skip build/aggregate, useful for dev)

**`--skip_aggregate` flag:**
- Without flag (default): aggregates cache for ALL discovered datasets.
- With flag + all caches exist: skips aggregation entirely for fast startup.
- With flag + missing cache: errors with actionable instructions.

**Dependency installation** uses `rp.r._ensure_npm_installed()` (from the rp library)
to install Node.js + npm if missing, instead of fragile bash checks. Import via
`import rp.r` since the ensure functions are private.

The startup summary prints per-dataset sample counts from `cache/cache_manifest.json`.

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
- **CSS mask-image needs real dimensions**: Setting `height: 0` with `overflow: visible` makes the element visually invisible because CSS mask-image requires actual element area to render. Solution: use a small placeholder wrapper for layout, absolute-position the full-size masked element on top.
- **Ghost preview sections**: Never declare a preview section for an artifact that isn't actually generated. The raft_flow processor declared `flow_sprite.jpg` but only produces `flow_stats.json` (numeric data). The preview section referenced a non-existent file, causing 404 errors in the UI.
- **JS pure functions must follow the same standards as Python**: All JS utility functions must be labeled as pure, have JSDoc with examples, and live in shared modules (`format.js`, `fields.js`) — not inline in Svelte components.
- **Event-based video sync is fundamentally broken**: Listening for play/pause/seeked on ALL videos and propagating creates infinite loops and flickering — even with a reentrant guard flag — because `currentTime` assignment triggers `seeked` events asynchronously. The correct approach is master-slave: only the first video has controls, others have no event listeners. A `requestAnimationFrame` loop corrects drift > 100ms. This is the standard approach in professional video comparison tools.
- **Bash argument parsing is fragile**: Unknown args like `--google` silently fell through to the port variable. Moved all arg parsing to Python Fire, which auto-validates, type-checks, and generates `--help`.

## TODO

### Dirty Tracking for Fast Server Boot

**Problem**: `run.sh` runs the aggregator before every server boot, which does a full filesystem scan of all 65K+ shard buckets under `samples/`. This takes minutes even when nothing has changed, because the aggregator's only way to find unaggregated samples is to walk the entire directory tree and diff against `cache_manifest.json`. The processing pipeline's `auto_aggregate` avoids this (passes `sample_list=` directly), but if a batch is interrupted before auto-aggregate fires, those samples are orphaned — on disk but not in cache.

**Solution**: Explicit `.dirty` marker files at three levels of the shard hierarchy.

**How it works**:

1. **When any artifact is written to a sample dir**, the writing code touches `.dirty` files at all three levels:
   - `samples/<s1>/<s2>/<sample_id>/.dirty` — this sample has unaggregated artifacts
   - `samples/<s1>/<s2>/.dirty` — some sample in this bucket is dirty
   - `samples/<s1>/.dirty` — some bucket in this shard is dirty

2. **Where to put the touch logic**: in the lowest-level artifact-writing code (e.g., `ensure_sample_dir()` in `base.py`, or wherever files are written to sample dirs). This way every processor — current and future — automatically marks samples dirty without having to remember. No processor-level code changes needed.

3. **Auto-aggregate cleans markers**: after successfully aggregating a batch, delete `.dirty` from each aggregated sample dir. If a shard's bucket has no more dirty samples, clean the bucket's `.dirty`. If a shard has no more dirty buckets, clean the shard's `.dirty`. (Walk up and clean if empty.)

4. **On server boot** (in `run.sh` or aggregator):
   - **No `.dirty` files at shard level** → skip aggregator entirely, cache is current. O(1) check: `ls samples/*/.dirty 2>/dev/null`.
   - **Some `.dirty` shards found** → only descend into those shards, find dirty buckets, find dirty samples. Aggregate only those. Proportional to interrupted work, not total dataset size.
   - **Fallback**: `--rebuild` flag still does full scan + `--clear_cache` for when you need it.

5. **Interrupted batch scenario** (the motivating case):
   - Pipeline processes 300 of 500 samples in a batch, writes artifacts to sample dirs
   - Each artifact write touches `.dirty` up the shard tree
   - User interrupts before auto-aggregate
   - Next server boot: aggregator finds ~300 dirty samples via `.dirty` markers, aggregates just those, cleans markers
   - Server starts with up-to-date cache

**Key properties**:
- Clean boot (no interrupted work) = instant, no scanning
- Dirty boot = proportional to orphaned samples, not total dataset
- Impossible to forget marking dirty (lives in shared write code)
- Aggregation cleanup is straightforward (delete markers bottom-up)
- `.dirty` files are tiny (empty, just the inode) and gitignored

(See Glossary at top of manifest for all term definitions.)

### Code Audit Fix Plan

Derived from a 10-agent frenzy audit, then each item verified against actual v2 code.
Prioritized by impact-to-code-added ratio. Minimal additions, maximal robustness.

**Security**: Completely irrelevant. Local-only app, no auth, no internet exposure. Non-concern.
Never prioritize security work in this project.

**Skipped items** (not worth the code):
- B3 (export all endpoint) — NOW NEEDED. "Export All" was broken: it only exported the current page because `$currentResults` is one page of results. Requires a server-side endpoint (`/api/export/names`) that runs the same search+filters but returns only video names without pagination/enrichment.
- B7 (getsize FUSE crash) — hypothetical. Never actually observed this crash. Skip for now.
- D2 (concurrent aggregation lock) — `fcntl.flock()` is unreliable on NFS/FUSE (may silently
  not lock, or hang forever). Just don't run two aggregators simultaneously. Add a comment.
- B6 (underscore split) — only affects dataset names containing underscores. We only have `pexels`.
- R3 (dataset validation 7x) — each occurrence is one line. Extracting adds a function definition
  + Flask error handler. More code than it saves.
- R7 (result formatting 3x) — each is 2-3 lines. Marginal savings.
- R8 (fieldLabel/fieldDescription/fieldDtype) — three small functions in `frontend/src/lib/fields.js`
  with different fallback values (`key.replace(/_/g, ' ')` vs `''` vs `'float'`). Clear as-is.
- SH5 (user_data gitignore) — already works correctly (`/user_data` in .gitignore).

**HALLUCINATED bugs** (reported by audit agents but confirmed NOT real in v2):
- B1 — "sort_results drops items with missing sort values": `sort_results` already uses
  `with_val`/`without_val` pattern at search.py:350-358 — missing values go at end, not dropped.
- B2 — "apply_filters uses continue instead of break": `apply_filters` already uses
  `passed = False; break` at search.py:280-285.
- B4 — "SearchHeader sort uses one-shot initializer": Already uses reactive `$:` block with
  `_lastSort` guard variable in SearchHeader.svelte.

---

#### Step 1: DRY violations (net code reduction)

**R1 — Histogram binning duplicated**
- Files: `server/app.py` lines 577-583 (`compute_histograms`) and lines 401-408
  (`compute_result_histograms`)
- Problem: Identical binning loop in both:
  ```python
  bucket_size = (hi - lo) / bins if hi > lo else 1
  counts = [0] * bins
  for v in values:
      idx = min(bins - 1, max(0, int((v - lo) / bucket_size)))
      counts[idx] += 1
  ```
  Only difference: `compute_histograms` computes lo/hi from `min(values)`/`max(values)`,
  while `compute_result_histograms` reads lo/hi from pre-computed `metadata_stats`.
  The binning loop itself is character-for-character identical.
- Fix: Extract to `server/search.py`:
  ```python
  def bin_values(values, lo, hi, bins):
      """
      Bin numeric values into histogram counts. Pure function.
      (list[float], float, float, int) → list[int]

      >>> bin_values([1, 2, 3, 4], 0, 4, 4)
      [1, 1, 1, 1]
      >>> bin_values([], 0, 10, 5)
      [0, 0, 0, 0, 0]
      """
      bucket_size = (hi - lo) / bins if hi > lo else 1
      counts = [0] * bins
      for v in values:
          idx = min(bins - 1, max(0, int((v - lo) / bucket_size)))
          counts[idx] += 1
      return counts
  ```
  Both callers pass their own lo/hi and call `bin_values(values, lo, hi, bins)`.

**R2 — searchFuzzy/searchClip identical**
- File: `frontend/src/lib/api.js` lines 21-33
- Problem: `searchFuzzy` and `searchClip` are identical except for the URL path segment
  (`/api/search/fuzzy` vs `/api/search/clip`). Same query string construction, same
  `checkedJson` call.
- Fix:
  ```javascript
  async function searchWithEndpoint(endpoint, dataset, query, params) {
    const filterQS = filtersToQueryString(params.filters);
    const paginationQS = paginationToQueryString(params);
    const resp = await fetch(
      `/api/search/${endpoint}?dataset=${dataset}&q=${encodeURIComponent(query)}${filterQS}${paginationQS}`
    );
    return checkedJson(resp);
  }
  export const searchFuzzy = (d, q, p) => searchWithEndpoint('fuzzy', d, q, p);
  export const searchClip = (d, q, p) => searchWithEndpoint('clip', d, q, p);
  ```

**R4 — CLIP_MODEL duplicated + clip_encoder.py breaks plugin isolation** ✅ RESOLVED
- Was: `server/clip_encoder.py` hardcoded CLIP knowledge outside the plugin.
- Fix: Text encoding is now part of the processor plugin contract. `Processor` base class
  has optional `embedding_space` dict and `encode_text()` staticmethod. `ClipProcessor`
  overrides both. Server discovers text encoders generically via `collect_text_encoders()`.
  `server/clip_encoder.py` deleted. `CLIP_MODEL` lives only in `clip.py`.
- Why the server needs text encoding: at search time, the user's text query must be encoded
  into the same embedding space as the pre-computed image embeddings. Currently only CLIP,
  but future embedding types will be added (VideoCLIP, Gemini text embeddings, etc.).
- Fix: Make text encoding part of the processor plugin contract.
  1. Add optional `embedding_space` dict and `encode_text()` staticmethod to `Processor` base class:
     ```python
     class Processor(ABC):
         # ... existing ...
         embedding_space: dict = None  # Optional: {prefix, dim, model, description}

         @staticmethod
         def encode_text(query):
             """Override to provide text-to-embedding for search. Returns (D,) ndarray or None."""
             return None
     ```
  2. Move `clip_encoder.py`'s lazy-loading text encoder into `ClipProcessor.encode_text()`:
     ```python
     class ClipProcessor(Processor):
         name = "clip"
         embedding_space = {
             "prefix": "clip",
             "dim": 512,
             "model": "openai/clip-vit-base-patch32",
             "description": "CLIP ViT-B/32 cosine similarity",
         }

         @staticmethod
         def encode_text(query):
             """Encode text query into CLIP embedding space. Lazy-loads model on first call."""
             # ... the code currently in clip_encoder.py ...
     ```
  3. Server discovers text encoders generically at startup:
     ```python
     text_encoders = {}
     for name, proc_cls in discover_processors().items():
         if proc_cls.embedding_space and proc_cls.encode_text is not Processor.encode_text:
             prefix = proc_cls.embedding_space["prefix"]
             text_encoders[prefix] = proc_cls.encode_text
     ```
  4. Search routes use `text_encoders[index_name](query)` instead of `encode_text(query)`.
  5. Delete `server/clip_encoder.py`. `CLIP_MODEL` stays in `clip.py` only.
  When adding a new embedding type (e.g., VideoCLIP), just write a new processor with
  `embedding_space` and `encode_text`. The server picks it up automatically — no new routes,
  no new files, no edits to app.py.
- Implementation note: CommonSource (`libs/CommonSource`) has a CLIP module with lazy-loading
  text/image encoding. Check if it can be reused for `encode_text()` before reimplementing.
  If CommonSource's API is suitable, `ClipProcessor.encode_text` can delegate to it.
  If not (wrong model, missing features), implement directly in the processor.

**R5 — L2 normalization repeated 4x**
- Verified 4 occurrences in `server/`:
  1. `app.py:616-618` — single query vector, `norm > 0` guard
  2. `search.py:150-152` — single query vector, `norm > 0` guard (in `clip_search`)
  3. `search.py:176-178` — single centroid vector, `norm > 0` guard (in `convex_hull_search`)
  4. `search.py:182-184` — batch normalization with `np.maximum(norms, 1e-8)` clamp
- Occurrences 1-3 are identical pattern. Occurrence 4 is a batch version with different
  zero-handling (clamp instead of skip).
- Fix: Extract to `server/search.py`:
  ```python
  def l2_normalize(vec):
      """
      L2-normalize a vector or batch of vectors. Zero vectors unchanged. Pure function.
      (..., D) float32 → (..., D) float32

      >>> import numpy as np
      >>> l2_normalize(np.array([3.0, 4.0]))
      array([0.6, 0.8])
      >>> l2_normalize(np.array([0.0, 0.0]))
      array([0., 0.])
      """
      norm = np.linalg.norm(vec, axis=-1, keepdims=True)
      return np.where(norm > 0, vec / norm, vec)
  ```
  Works for single vectors (shape `(D,)` or `(1, D)`) and batches (shape `(N, D)`).
  `np.where` handles the zero-vector case for both. Replace all 4 call sites.

**R6 — GPU logger closure duplicated in 2 processors**
- `preprocess/processors/clip.py:116-118` and `preprocess/processors/raft_flow.py:75-77`
- Verified character-for-character identical:
  ```python
  def log(msg):
      ts = datetime.now().strftime("%H:%M:%S")
      print(f"  [{ts}] GPU {gpu_id}: {msg}", flush=True)
  ```
  Both also import `from datetime import datetime` identically.
- Fix: Add to `preprocess/processors/base.py`:
  ```python
  def make_gpu_logger(gpu_id):
      """Create a timestamped GPU logger closure. Returns callable(msg)."""
      from datetime import datetime
      def log(msg):
          ts = datetime.now().strftime("%H:%M:%S")
          print(f"  [{ts}] GPU {gpu_id}: {msg}", flush=True)
      return log
  ```
  Both processors: replace the closure + import with `log = make_gpu_logger(gpu_id)`.

#### Step 2: Dead code (pure deletion)

- **DC1**: Delete `sortResults` (line 37) + `mulberry32` (line 22) from `frontend/src/lib/sort.js`.
  `sortResults` is exported but imported nowhere in the codebase. `mulberry32` is only called
  by `sortResults`. If the file becomes empty after deletion, delete the file.
- **DC2**: Delete `selectedCount` from `frontend/src/lib/stores.js:46`.
  `export const selectedCount = derived(selectedVideos, $s => $s.size)` — exported, never imported.
- **DC3**: Remove `showExport` from `frontend/src/App.svelte:3` import destructuring.
  Imported from stores.js but never referenced in the component body or template.
- **DC4**: Remove `fieldInfo` from `frontend/src/components/SyntaxHelp.svelte:2` import.
  `import { showHelp, currentSort, fieldInfo }` — `fieldInfo` never used in the file.
- **DC5**: Delete `let open = false;` from `frontend/src/components/widgets/Popover.svelte:10`
  and its assignments at lines 45 (`open = true`) and 50 (`open = false`). Variable is written
  but never read — no `{#if open}`, no binding, no reactive statement consumes it.
- **DC6**: Delete 3 broken test files that import v1 APIs no longer in v2:
  - `tests/benchmark_ingest.py` — imports `ensure_sample_dir` from `video_utils` (now a method on Processor)
  - `tests/bench_pyav_ingest.py` — same broken import
  - `tests/profile_ingest.py` — imports `resize_by_height`, `compose_sprite`, `resize_contain`
    from `video_utils` (renamed to `*_cv2` and moved to ingest.py in v2)
  Keep: `tests/bench_gpu_decode.py`, `tests/bench_gpu_subprocess.py`, `tests/compress_ladder.py`
  (standalone, no broken imports).

#### Step 3: Tiny high-impact bug fixes

**B5 — Score histogram missing from result histograms** (2 lines)
- File: `server/app.py:390-396` in `compute_result_histograms`
- Problem: Collects values from `r.get("metadata")` and `r.get("stats")` but NOT from
  `r.get("score")`. The `score` field (CLIP cosine similarity) is a top-level key on result
  dicts, not nested under metadata or stats. So score never appears in result histograms.
- Fix: Add before the source loop:
  ```python
  for r in results:
      if "score" in r and isinstance(r["score"], (int, float)):
          fields.setdefault("score", []).append(r["score"])
      for source in [r.get("metadata") or {}, r.get("stats") or {}]:
          ...
  ```

**D5 — Zero vectors pollute FAISS index** (2 lines)
- File: `preprocess/processors/clip.py:173-175`
- Problem: When an image fails to load, `_load_image` returns None, so it's excluded from
  the CLIP forward pass. But at line 173, `emb_map.get((j, frame_idx), np.zeros(CLIP_DIM, ...))`
  falls back to a zero vector for missing frames. Line 175 saves this zero vector to the .npy
  file unconditionally. The aggregator reads it, adds it to FAISS → garbage similarity scores.
- Fix: Check `emb_map` membership before saving, not a norm check:
  ```python
  if (j, frame_idx) in emb_map:
      np.save(os.path.join(sd, frame_files[frame_idx]), emb)
  ```
  The aggregator already handles missing .npy files (no file = no vector added).
  This also means `clip_std` should only be computed from valid embeddings — guard similarly.

#### Step 4: Atomic writes (prevents cache corruption on crash)

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!!! CRITICAL: SAME-MOUNT REQUIREMENT FOR ATOMIC WRITES                         !!!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

`os.rename()` is only atomic when source and dest are on the same filesystem.
If the temp file is on `/tmp` (local disk) but the target is on NFS, the rename
becomes a copy+delete — NOT atomic. The temp file MUST be created in the same
directory as the target file. This is why `tempfile.mkstemp(dir=dir_name)` passes
the target's directory. NEVER use `tempfile.mkstemp()` without `dir=` for atomic
writes. The existing `save_json_atomic` already does this correctly.

**D1 + D6 — Abstract the atomic write pattern**

The existing `save_json_atomic` in `video_utils.py` and the new `save_npz_atomic`,
`save_faiss_atomic`, `save_npy_atomic` all share identical boilerplate: mkstemp in same
dir, write to tmp, rename, cleanup on exception. Abstract to one generic helper:

```python
def atomic_write(path, writer_fn, suffix=".tmp"):
    """
    Atomic file write: create temp in same directory, write, rename.
    writer_fn(tmp_path) performs the actual write. os.rename is atomic on
    POSIX when source and dest are on the same filesystem — which is guaranteed
    because mkstemp uses the same directory as the target.

    NEVER call tempfile.mkstemp() without dir= for this pattern.
    """
    dir_name = os.path.dirname(path) or "."
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dir_name, suffix=suffix)
    os.close(fd)
    try:
        writer_fn(tmp)
        os.rename(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
```

Then all specific savers become thin wrappers:

```python
def save_json_atomic(data, path):
    """Atomic JSON save."""
    def write(tmp):
        with open(tmp, "w") as f:
            json.dump(data, f)
    atomic_write(path, write)

def save_npy_atomic(array, path):
    """Atomic numpy .npy save."""
    atomic_write(path, lambda tmp: np.save(tmp, array), suffix=".tmp.npy")

def save_npz_atomic(path, **arrays):
    """Atomic numpy .npz save."""
    atomic_write(path, lambda tmp: np.savez_compressed(tmp, **arrays), suffix=".tmp.npz")

def save_faiss_atomic(index, path):
    """Atomic FAISS index save."""
    import faiss
    atomic_write(path, lambda tmp: faiss.write_index(index, tmp), suffix=".tmp.faiss")
```

**D1 — Non-atomic FAISS/npz writes in aggregator**
- `aggregator.py:245`: `np.savez_compressed(emb_path, ...)` → `save_npz_atomic(emb_path, embeddings=all_embs)`
- `aggregator.py:252`: `faiss.write_index(index, index_path)` → `save_faiss_atomic(index, index_path)`

**D6 — Per-sample writes non-atomic in ALL processors**
- Verified 6 non-atomic writes. Zero processors currently use `save_json_atomic`:
  1. `raft_flow.py:133` — `json.dump(stats, f)` for `flow_stats.json`
  2. `clip.py:180` — `json.dump({"clip_std": clip_std}, f)` for `clip_std.json`
  3. `phash.py:50` — `json.dump(stats, f)` for `phash_stats.json`
  4. `base.py:154` — `json.dump({...}, f)` for `origins.json`
  5. `ingest.py:334` — `json.dump(proxy_meta, f)` for `metadata.json`
  6. `clip.py:175` — `np.save(...)` for clip embedding .npy files
- Fix: Replace all 5 `json.dump` sites with `save_json_atomic(data, path)`.
  Replace the `np.save` with `save_npy_atomic(array, path)`.
  Import from `video_utils` in each processor file.

#### Step 5: Aggregator correctness

**D3 — Failed samples marked as "included" in cache manifest**
- File: `preprocess/aggregator.py` lines 296-309, 340-341
- Problem: At line 299, `all_sids = sorted(prev_names | {sid for sid, _ in sample_list})`
  adds ALL sample IDs to the inclusion set regardless of whether their data was actually
  read. The aggregation functions (`aggregate_json_dict`, `aggregate_vector_index`) silently
  skip samples with missing files, but the ID is already in `all_sids`. At line 341,
  `"samples_included": all_sids` saves this inflated set. Result: next run sees the sample
  as "already included", skips it, data permanently missing.
- Fix: Track successful aggregations. Modify `aggregate_json_dict` to return
  `(count, successful_sids)` where `successful_sids` is the set of sample IDs that had
  non-empty data. Same for `aggregate_vector_index`. In `aggregate()`, build the final
  `samples_included` from `prev_names | union(all_successful_sids)` instead of `all_sids`.
  Concrete changes:
  - `aggregate_json_dict`: add `included = set()`, `included.add(sid)` when `sample_data`
    is non-empty (line 164), return `(len(merged), included)` instead of `len(merged)`
  - `aggregate_vector_index`: add `included = set()`, `included.add(sid)` when `vec is not None`
    (line 228), return `(count, included)` instead of `count`
  - `aggregate()`: collect all returned sets, union them, use for `samples_included`

**D4 — Scoped aggregation (`only_processors`) marks samples as globally included**
- File: `preprocess/aggregator.py` lines 316-321, 340
- Problem: When `only_processors=["clip"]` is used (e.g., auto-aggregation after a clip batch),
  lines 316-321 filter which aggregation rules run (only clip's rules). But line 341 still
  writes ALL new sample IDs to `samples_included`. Next full aggregation sees these samples
  as "already included" and skips them — but phash/raft_flow rules never ran for them.
- Fix: When `only_processors` is set, do NOT add new samples to `samples_included`. Only
  full (unscoped) aggregation marks samples as globally included:
  ```python
  if only_processors is not None:
      # Scoped aggregation: update cache data but don't claim full inclusion
      manifest["samples_included"] = sorted(prev_names)
  else:
      manifest["samples_included"] = sorted(prev_names | all_successful_sids)
  ```
  This is safe because re-aggregating an already-included sample is idempotent:
  `dict.update()` overwrites with same value, vector dedup replaces with same embedding.

#### Step 6: Docstrings & purity labels

**DOC1 — 7 mislabeled "Pure function" labels** (not 16 as originally reported)
- Verified the actual offenders. 4 of them already say "Pure function (reads filesystem)" —
  an oxymoron. The fix is to drop "Pure function" and keep "Reads filesystem":
  1. `aggregator.py:36` `list_shard_pairs` — "Pure function (reads filesystem)" → "Reads filesystem"
  2. `aggregator.py:59` `discover_sample_dirs` — "Pure function (reads filesystem)" → "Reads filesystem"
  3. `aggregator.py:96` `read_sample_json` — "Pure function (reads filesystem)" → "Reads filesystem"
  4. `aggregator.py:111` `read_sample_numpy` — "Pure function (reads filesystem)" → "Reads filesystem"
  5. `app.py:141` `load_favorites` — "Pure function (reads filesystem)" → "Reads filesystem"
  6. `app.py:175` `load_vector_indices` — "Pure function (reads filesystem)" → "Reads filesystem"
  7. `app.py:217` `load_json_dicts` — reads filesystem, fix label
- Borderline cases left alone: `needs_processing`, `filter_todo`, `select_video_source`,
  `count_satisfied_deps` — these use `os.path.exists()` which is minimal I/O. Arguable.

**DOC2 — 2 no-op doctests** (not 3 as originally reported)
- `server/search.py:146` (`clip_search`): `>>> isinstance(clip_search.__doc__, str)` / `True`
- `server/search.py:169` (`convex_hull_search`): same pattern
- Fix: Replace with meaningful tests:
  ```python
  # clip_search
  >>> import faiss
  >>> idx = faiss.IndexFlatIP(3)
  >>> idx.add(np.array([[1,0,0],[0,1,0]], dtype=np.float32))
  >>> results = clip_search([1, 0, 0], idx, ["a", "b"], k=2)
  >>> results[0]["video_name"]
  'a'

  # convex_hull_search
  >>> embs = np.array([[1,0,0],[0,1,0],[0.9,0.1,0]], dtype=np.float32)
  >>> results = convex_hull_search(embs[:1], embs, ["a","b","c"], k=3)
  >>> results[0]["video_name"]
  'a'
  ```

**DOC3 — 2 pure functions missing doctests**
- `preprocess/video_utils.py:43` `sample_dir` — has docstring but no `>>>` example.
  Add: `>>> 'samples' in sample_dir('/data/pexels', '19012581')` / `True`
- `preprocess/processors/raft_flow.py` `_resize_for_flow` — add input/output shape doctest.

**DOC4 — Missing shape annotations on array-transforming functions**
- Per project conventions, functions that transform arrays MUST document shapes.
- `clip_search`: `(D,) or (1, D) float32, faiss.Index, list[str] → list[{video_name, score}]`
- `convex_hull_search`: `(K, D) float32, (N, D) float32, list[str] → list[{video_name, score}]`
- `l2_normalize` (new): `(..., D) float32 → (..., D) float32`
- `split_grid`: already has shape annotation, leave alone.

#### Step 7: Setup & scripts

**SH3 — Bare python3 in run.sh**
- File: `run.sh:48` — `SAMPLE_COUNT=$(python3 -c "import json; ...")` uses bare `python3`.
- Fix: Replace with `uv run python`. One word change.

**SH4 — uv.lock gitignored**
- File: `.gitignore:8` — `uv.lock` is listed.
- Fix: Remove the line. Run `git add uv.lock` to commit the lockfile for reproducible builds.

**SH6 — Unused dependencies in pyproject.toml**
- Verified against all imports in the codebase. 5 completely unused (zero imports anywhere):
  `requests`, `torchvision`, `py3nvml`, `easydict`, `einops`
- Test-only deps (used only in files we're keeping or deleting):
  - `decord2` — only in `benchmark_ingest.py` (being deleted in DC6). Remove.
  - `psutil` — only in `profile_ingest.py` (being deleted in DC6). Remove.
  - `pyinstrument` — only in `profile_ingest.py` (being deleted in DC6). Remove.
  - `pynvvideocodec` — only in `bench_gpu_decode.py` and `bench_gpu_subprocess.py` (keeping).
    Keep as optional dep or remove and let those benchmarks fail until manually installed.
- Fix: Remove at minimum the 5 unused + 3 test-only-in-deleted-files = 8 deps. Run `uv lock`.

**SH7 — opencv-python + opencv-contrib-python conflict**
- `pyproject.toml:17-18` lists both. `opencv-contrib-python` is a strict superset.
- Fix: Remove `opencv-python`, keep `opencv-contrib-python`. Run `uv lock`.

**SH1/SH2 — Setup script gaps**
- Node.js: Add comment to `run.sh` noting the requirement. Use `rp call ensure_node_installed`
  in the frontend build section.
- CommonSource: Add comment to `setup.sh` with the git clone command.
- These are comments, not code. Minimal additions.

---

#### Phase 3: Dirty Tracking Implementation

Depends on Steps 4-5 (atomic writes, correct inclusion tracking) being complete.
See "Dirty Tracking for Fast Server Boot" section above for the full design.

Implementation steps:

1. **Add `touch_dirty(sample_path)` to `video_utils.py`**: touches `.dirty` at sample, bucket,
   and shard levels. Three `open(path, 'a').close()` calls.

2. **Call `touch_dirty()` in `ensure_sample_dir()` in `base.py`**: every processor calls
   `ensure_sample_dir()` before writing artifacts. Guarantees markers exist before any write.

3. **Add `clean_dirty(sample_dirs)` to aggregator**: after successful aggregation, delete
   `.dirty` from each sample dir. Walk up: if bucket has no dirty samples, clean bucket's
   `.dirty`. If shard has no dirty buckets, clean shard's `.dirty`.

4. **Add `find_dirty_samples(samples_dir)` to aggregator**: fast scan — only descend into
   shard dirs with `.dirty`, then bucket dirs with `.dirty`. Replaces `discover_sample_dirs()`
   for boot-time check. O(dirty samples) not O(total samples).

5. **Update `run.sh`**: replace unconditional aggregator with dirty check:
   ```bash
   DIRTY_COUNT=$(find datasets/pexels/samples -maxdepth 1 -name ".dirty" 2>/dev/null | wc -l)
   if [ "$DIRTY_COUNT" -gt 0 ]; then
       echo "Found dirty shards, aggregating..."
       uv run python preprocess/aggregator.py --dataset_dir datasets/pexels --dirty_only
   else
       echo "Cache is current, skipping aggregation."
   fi
   ```

6. **Add `.dirty` to `.gitignore`**: `**/.dirty`

7. **Test**: process batch → verify markers → aggregate → verify cleanup → restart → verify fast boot.

---

## How to Add a New Dataset Plugin (Step-by-Step)

### 1. Create the directory and module

```bash
mkdir -p datasets/my_dataset
```

Create `datasets/my_dataset/__init__.py`:

```python
"""
My Dataset — description of the dataset.
"""
import csv
import os
from datasets import VideoDataset

# Path to external source (if videos need to be hardlinked from elsewhere)
SOURCE_DIR = "/path/to/external/videos"

class MyDataset(VideoDataset):
    name = "my_dataset"           # Must match folder name
    human_name = "My Dataset"     # Shown in frontend dropdown
    fields = {}                   # Dataset-native fields (see below)
    help_text = (
        "Description shown in the frontend help panel. "
        "Origin, format, size, characteristics."
    )

    def entries(self):
        """Return list of {video_name, caption, source_path} dicts."""
        csv_path = os.path.join(os.path.dirname(__file__), "data.csv")
        videos_dir = os.path.join(os.path.dirname(__file__), "videos")
        result = []
        with open(csv_path) as f:
            for row in csv.DictReader(f):
                video_file = os.path.join(videos_dir, f"{row['id']}.mp4")
                if os.path.exists(video_file):
                    result.append({
                        "video_name": row["id"],
                        "caption": row["description"],
                        "source_path": os.path.abspath(video_file),
                    })
        return result

    def prepare(self):
        """Hardlink videos from external source. Idempotent."""
        videos_dir = os.path.join(os.path.dirname(__file__), "videos")
        os.makedirs(videos_dir, exist_ok=True)
        # Read your source data, hardlink each video:
        # os.link(src, dst) with symlink fallback
```

### 2. Copy source data into the dataset folder

Place your CSV/JSON/metadata files in `datasets/my_dataset/`. These are gitignored
by `datasets/**/*.csv` pattern. The `__init__.py` is tracked.

### 3. Prepare and build manifest

```bash
uv run python prepare_dataset.py my_dataset
```

This runs `prepare()` (hardlinks videos) and `build_manifest()` (writes manifest.json).

### 4. Process videos

```bash
uv run python preprocess/process_all.py \
    --process=ingest \
    --dataset_dir=datasets/my_dataset \
    --manifest=datasets/my_dataset/manifest.json \
    --batch_size=100
```

Use `--process=ingest` for basic processing (compress + ingest due to deps).
Add `--process=clip,phash` etc. for more.

### 5. Verify

```bash
uv run python -c "
from server.app import load_dataset
ds = load_dataset('my_dataset', 'datasets')
print(f'Loaded: {len(ds[\"entries\"])} entries, {len(ds[\"video_metadata\"] or {})} metadata')
"
```

### Common Pitfalls

- **`name` must match folder name** — `datasets/web360/` → `name = "web360"`
- **`entries()` must return dicts with `video_name`, `caption`, `source_path`** — these
  are required by `VideoDataset`. Missing fields → `ValueError` from `validate_entries()`.
- **Videos must exist on disk** — `source_path` must point to real files. Use hardlinks
  in `prepare()` for self-containment.
- **Field name collisions** — Dataset field names cannot match any processor field name.
  Checked at server boot. If collision, rename the field in your dataset module.
- **Manifest.json is auto-generated** — Don't hand-edit it. Edit `entries()` instead.
- **CSV/data files are gitignored** — Track `__init__.py`, not the raw data.

---

## How to Add a New Processor Plugin (Step-by-Step)

### 1. Create the processor file

Create `preprocess/processors/my_processor.py`:

```python
"""
My Processor — what it computes, why, how.
"""
import os
import json
import fire
from preprocess.processors.base import Processor, run_pool_with_progress
from preprocess.video_utils import sample_dir, save_json_atomic

class MyProcessor(Processor):
    name = "my_proc"
    human_name = "My Processor"
    depends_on = ["ingest"]       # Must run after ingest (needs thumbnails)

    artifacts = [
        {"filename": "my_stats.json", "label": "My Stats",
         "description": "Computed statistics", "type": "data"},
    ]

    fields = {
        "my_field": {"label": "My Field", "description": "What this measures",
                     "dtype": "float"},
    }

    aggregation = [
        {"type": "json_dict", "source": "my_stats.json",
         "target": "video_stats.json"},
    ]

    def process(self, entries, dataset_dir, workers=32):
        args = [(e, dataset_dir) for e in entries]
        run_pool_with_progress(_worker, args, self.human_name, workers)

def _worker(args):
    entry, dataset_dir = args
    sd = sample_dir(dataset_dir, entry["video_name"])
    # ... compute something ...
    save_json_atomic({"my_field": 42.0}, os.path.join(sd, "my_stats.json"))
    return entry["video_name"], True, None

if __name__ == "__main__":
    fire.Fire({"main": MyProcessor.cli_main})
```

### 2. That's it — it auto-discovers

`discover_processors()` scans the directory. No registration needed.

### 3. Run it

```bash
uv run python preprocess/process_all.py --process=my_proc --dataset_dir=datasets/pexels
```

Dependencies are auto-resolved (ingest → compress will also run if needed).

### Embedding Processor (with text search)

To add a new embedding model that supports text search:

```python
class MyEmbeddingProcessor(Processor):
    name = "my_embed"
    embedding_space = {
        "prefix": "my_embed",
        "dim": 768,
        "model": "my-model-name",
        "description": "My embedding model description",
    }

    aggregation = [
        {"type": "vector_index", "source": "my_embedding.npy",
         "prefix": "my_embed", "dim": 768},
    ]

    @staticmethod
    def encode_text(query):
        \"\"\"Encode text into embedding space. Lazy-load model.\"\"\"
        # ... load model, tokenize, encode, return (768,) float32 ...
```

The server auto-discovers it. The frontend auto-adds a mode tab for it.

### Common Pitfalls

- **Artifact filenames must be unique across all processors** — Validated at boot.
- **Field names must be unique across all processors AND datasets** — Validated at boot.
- **GPU processors must use subprocess isolation** — Use `run_gpu_subprocess()` from base.
- **All JSON writes must use `save_json_atomic()`** — For crash safety on NFS.
- **Fire CLI at the bottom is required** — Enables standalone execution.
- **`process()` must only touch the given entries** — Never scan all samples.
- **`depends_on` must list real processor names** — Circular deps are detected and error.

---

## Upcoming: Dataset Plugin Architecture

### Motivation

The current `manifest.json` is a flat list of `{video_name, caption, source_path}` — it's
hardcoded to Pexels and has no concept of different dataset types with different fields.
We need to support multiple datasets (Pexels, Web360, future image datasets) where each
dataset may have unique fields, different source formats, and different requirements.

### Design: Datasets as Python Modules

Each dataset is a Python module under `datasets/<name>/` with an `__init__.py` that
subclasses a base class. Just like processors — drop a module, zero registration needed.

```
datasets/
  pexels/
    __init__.py            # class PexelsDataset(VideoDataset): ...
    manifest.json          # raw data (CSV, JSON, whatever the source provides)
    samples/               # per-sample artifacts (same as now)
    cache/                 # aggregated cache (same as now)
  web360/
    __init__.py            # class Web360Dataset(VideoDataset): ...
    metadata.csv           # raw data from Web360 dump
    samples/
    cache/
```

### Base Class Hierarchy

```python
class Dataset(ABC):
    """Base class for all datasets."""
    name: str              # Machine name: "pexels", "web360"
    human_name: str        # Display name: "Pexels", "Web360"
    fields: dict           # {field_name: {label, description, dtype}} — dataset-native fields

    @abstractmethod
    def entries(self) -> list[dict]:
        """Yield all entries. Each entry must have at minimum: video_name."""
        ...

class VideoDataset(Dataset):
    """Mixin for video-based datasets. Adds video-specific requirements."""
    # Requires: video_name, caption, source_path per entry
    # Processors that depend on video data check isinstance(dataset, VideoDataset)
```

### Key Principles

- **Dataset defines its own fields** — not raw JSON dump. The Python module chooses which
  fields to expose, how to name them, and their types. Raw source format is internal.
- **A sample = dataset fields + processor fields + processor artifacts.** The sum of
  everything the dataset provides and everything processors compute.
- **Collision checking at boot** — dataset fields vs processor fields, dataset artifacts vs
  processor artifacts. No name may appear in both. ValueError at startup if violated.
- **Fields work identically in UI** — dataset fields appear in histograms, filters, sort
  just like processor fields. Partial coverage is fine (not every sample has every field).
- **Processors are dataset-agnostic** — they operate on artifacts (thumbnails, sprites),
  not on dataset-specific metadata. A processor that needs video frames works on any
  VideoDataset.
- **Videos are hardlinked into samples/** — self-contained, no external path dependencies.

### Web360 Integration (POC)

Source: `/root/CleanCode/Dumps/Web360/datasets/web360`
- Small dataset, quick to process
- Basic processing only: compress + ingest (no CLIP, no RAFT)
- 1-2 dataset-specific fields if valuable
- Hardlink videos into `datasets/web360/samples/`
- Should appear alongside Pexels in the UI dropdown

### Upcoming: Frontend Embedding Model Decoupling

The frontend hardcodes "CLIP" in several places. This breaks plugin isolation — the
only place that mentions CLIP should be `preprocess/processors/clip.py`.

**Requirement:** The frontend must dynamically discover available embedding models
from the server. No hardcoded model names.

**API change:** Add `GET /api/embedding_models` returning available text encoders
with metadata from `embedding_space` dicts. Frontend fetches on mount.

**UI design:** The search mode switcher currently shows "Fuzzy / CLIP / Hull".
- With one embedding model: "Fuzzy / [model_name] / Hull" — looks the same as now
- With multiple models: the semantic search button becomes a split button or shows
  a small dropdown to select which model. Hull mode uses the selected model.
- All error messages and help text use the model name from the API, not hardcoded.

This makes the system fully pluggable: add a new embedding processor, server discovers
it, frontend shows it — zero edits to any other file.

### Upcoming: Hull Search Documentation

"Hull" / "convex hull" search is a MISNOMER. It is actually **centroid nearest-neighbor**:
1. Compute mean of selected embeddings → centroid
2. L2-normalize centroid (project onto unit sphere)
3. Cosine similarity of all vectors to centroid
4. Return top-k

No actual convex hull is computed. In 512-dim space, a convex hull of K<512 points
has zero volume — nothing would ever "fall inside" it. The centroid approach works
because selecting K similar videos places the centroid deep in that concept region.

**Action items:**
- Update `convex_hull_search` docstring to explain centroid-based approach
- Update frontend tooltip for Hull button to explain how it actually works
- Keep the name "Hull" in UI (short, established) but tooltip must be accurate

### Upcoming: Dataset-Native Artifacts

Datasets can bring their own per-sample file artifacts beyond video_name/caption/source_path.
For example, OpenHumanVid has pose annotations, segmentation masks, depth maps.

**Current state:** `ensure_sample_dir()` on the Processor base class creates the sample
directory, writes `origins.json`, and hardlinks `video.mp4` from `source_path`. This runs
during the first processor (compress). All processors call it. It works generically for
any dataset as long as `source_path` points to a real video file.

**The question:** How to get non-video dataset artifacts (poses, masks, etc.) into sample dirs?

**Option A: Extend `ensure_sample_dir()`** — Have it check the dataset module for declared
artifacts and copy/link them alongside `video.mp4`. Keeps sample creation in one place.
Pro: single source of truth for sample dir setup. Con: couples Processor base class to
Dataset modules (currently independent).

**Option B: Dataset `populate()` method** — Each dataset implements its own logic for
populating sample dirs with its artifacts. Called by the pipeline before processors run.
Pro: maximum flexibility per dataset. Con: duplicates shard routing / directory creation
logic, or requires importing it from video_utils.

**Option C: Do nothing until needed** — The numeric fields from datasets (aesthetic, blur,
etc.) already flow through manifest → entries → dataset_fields without needing files in
sample dirs. File-based artifacts (poses, masks) aren't blocking any current use case.
Add the feature when there's a concrete need. Pro: no premature abstraction. Con: delays
the feature if someone needs it soon.

**Current recommendation: Option C.** No concrete use case exists yet. Revisit when a
dataset with per-sample file artifacts needs to be displayed in the UI.

**Requirements (when implemented):**
- Dataset class declares `artifacts` list (same format as processors: {filename, label,
  description, type}). These are copied into sample dirs.
- Artifact names MUST NOT clash with processor artifact names. Validated at boot via
  `validate_no_collisions()`.
- Each artifact has a label and description (help string) visible in the UI.
- Image/video artifacts from datasets are shown in the detail panel (preview area)
  when a sample is double-clicked, alongside processor artifacts.
- Non-visual artifacts (pose JSON, etc.) listed as data artifacts.

### Upcoming: OpenHumanVid Integration

Source: another dump folder (likely `/root/CleanCode/Dumps/OpenHumanVid/` or similar).

**Key differences from Web360 POC:**
- Has more artifacts than just video: pose annotations, masks, etc.
- All artifacts must be copied/hardlinked into sample dirs with unique names
- Dataset module lists all artifacts with labels and descriptions
- Preview area in frontend shows all dataset artifacts (images, videos)
- Non-visual artifacts (pose JSON, etc.) are listed as data artifacts
- Process through compress + ingest at minimum

**Workflow:**
1. Find the dump, examine its contents and directory structure
2. Create dataset module with all artifacts declared
3. `prepare()` method hardlinks videos AND copies/hardlinks other artifacts
4. Collision check at boot ensures no name conflicts
5. Full testing alongside Pexels and Web360

### Modular Preview Pane (Implemented)

The detail/preview pane is a stack of collapsible sections where each section is
contributed by a processor or dataset. This enables datasets to show custom
visualizations (pose skeletons, depth maps, compression ladders, etc.).

**Architecture: Plugin-declared preview sections**

Each plugin declares `preview_sections` — a list of dicts with `type`, `label`,
`priority`, `description`, and `args`. The frontend renders them as collapsible
accordion items via generic renderer components.

```
frontend/src/components/preview/
  PreviewSection.svelte       — collapsible accordion wrapper (has tooltip from description)
  SectionRenderer.svelte      — maps type strings to renderer components
  SideBySideImages.svelte     — N images side by side with labels
  SideBySideVideos.svelte     — N videos with wrapping, sync, file sizes
  SingleImage.svelte          — one image, full width
  SingleVideo.svelte          — one video with controls
```

**Preview section declaration format:**
```python
preview_sections = [
    {"type": "side_by_side_videos",
     "label": "Compression Ladder",
     "priority": 50,
     "description": "H.264 veryfast CRF 28 proxies at multiple resolutions...",
     "args": {
         "files": ["compress_1080p.mp4", "compress_720p.mp4", ...],
         "labels": ["1080p", "720p", ...],
         "max_per_row": 3,        # wraps to multiple rows
         "sync": True,            # play/pause/seek syncs across all videos
         "show_filesize": True,   # shows file size next to each label
     }},
]
```

**Requirements and design decisions:**
- **Tooltips on section headers:** Each preview section header shows a native HTML
  tooltip (`title` attribute) with the `description` from the plugin. This lets users
  understand what they're looking at. Descriptions should mention artifact filenames.
- **Compression ladder shows ALL resolutions** (1080p, 720p, 480p, 360p, 240p, 144p),
  not just the first 3. Files that don't exist on disk are automatically hidden (e.g.,
  if a video was too small for 1080p, that entry won't appear).
- **Max 3 per row** with CSS flex wrapping — extra files go to the next row.
- **File sizes** shown next to labels in 50% opacity text (e.g., "1080p 2.3MB").
  Uses `humanFilesize()` in `format.js` matching rp's `human_readable_file_size` format
  (1024-based, integer when exact, 1 decimal otherwise).
- **Video sync:** Master-slave pattern with requestAnimationFrame drift correction.
  First video is the master (has controls), all others are slaves (no controls).
  RAF loop runs every frame, corrects slave `currentTime` only when drift > 100ms.
  Master's play/pause events propagate to slaves. No event listeners on slaves at all —
  this eliminates the feedback loops and flickering that event-based sync causes.
  Research frenzy (10 agents) confirmed this is the standard approach used by
  professional video comparison tools (Netflix VMAF viewer, Panopto, etc.).
  Previous attempt used event-based sync (play/pause/seeked propagation) which caused
  infinite loops and flickering because setting `currentTime` fires `seeked` events.
- **Only show existing files:** The component fetches file sizes from
  `/api/file_sizes/<dataset>/<video_name>` and only renders files that exist on disk.
  Ghost/missing artifacts are silently omitted.
- **No ghost preview sections:** A preview section must only reference artifacts that
  the processor actually generates. If a processor doesn't produce a visualization
  artifact, it must not declare a preview section for it. (Caught: raft_flow declared
  `flow_sprite.jpg` but never generates it — removed.)

**Key principle:** The preview pane has NO knowledge of specific processors or
artifacts. It renders generic section types. Adding a new visualization = drop a Svelte
renderer file, map a type string to it, have a plugin declare a section with that type.

### BirdsEye Logo

Custom SVG logo (`frontend/src/assets/birdseye.svg`) displayed in the header via CSS
mask-image for accent color inheritance.

**CSS approach:** A wrapper span (`.logo-wrap`) at text line height (1.2em × 1.2em)
provides the horizontal space in the flex layout. Inside it, the actual `.logo` span
is `position: absolute` at 3.25em × 3.25em (2.5× the text size), centered on the
wrapper. This makes the logo float vertically (doesn't push the header taller) while
still taking horizontal space (doesn't get clipped off-screen).

**Mistakes and corrections:**
1. First attempt: logo was `display: inline-block` at 3.25em height — pushed the
   entire header taller, creating whitespace above the search bar.
2. Second attempt: `position: absolute` with `right: 100%` — logo floated off the
   left edge of the screen, only half visible.
3. Third attempt: `height: 0` with `overflow: visible` — logo became invisible
   because CSS mask-image requires actual element dimensions to render.
4. Final solution: placeholder wrapper at text size + absolute-positioned logo at
   full size, centered on wrapper. Correct horizontal push, no vertical push, fully
   visible.

### Help Panel

The `?` button in the header toggles a help/info panel (`SyntaxHelp.svelte`). Its
tooltip reads "Help & dataset info" — it shows more than just search syntax:
- Search syntax reference (FZF, semantic, hull modes)
- Per-dataset help_text (descriptions from dataset plugins)
- General status and usage information

### Field Tooltip Source Attribution

All field tooltips (in FieldBar, detail panel, stats panel) show the origin plugin
in italic 50% opacity at the bottom of the tooltip. Format:
`Source: Ingest` or `Source: OpenHumanVid (HQ)`.

**Rationale:** When inspecting data in the frontend, the user needs to quickly
determine which plugin produced a given field — for debugging, understanding, and
tracing data provenance from the UI back to the processing pipeline. The source
annotation makes this immediately visible without needing to check code.

Implementation:
- Server tags each field with `"source"` in `/api/field_info` — processor fields
  get the processor's `human_name`, dataset fields get the dataset's `human_name`,
  server-computed fields (score) get "Server".
- `fieldTooltip(key)` in `fields.js` builds the HTML:
  `<strong>Label</strong><br/>Description<br/><span style="opacity:0.5;font-style:italic">Source: Name</span>`
- Used by DetailPanel, StatsPanel (replaces inline tooltip construction).

### Field Ordering

`FIELD_ORDER` in `fields.js` defines canonical field display order: height, width, duration, num_frames, file_size_mb, fps, clip_std, score, ... `sortFieldKeys()` pure function applies this ordering everywhere (stats panel, SPLOM, filter panel). Fields not in `FIELD_ORDER` appear after ordered fields in alphabetical order.

### Field Summary Format

Field summaries display `min … max` with unicode ellipsis (`\u2026`), no parentheses. In differential mode: `+/-diff Δ`.

### Statistics Panel Empty States

Zero fields can be selected (user controls field visibility via toggleable field bars). One-time initialization: `activeFields` is initialized to all fields on first data load, never auto-refilled after.

- **SPLOM** (no fields selected): "Select fields in the Analysis column to show the scatterplot matrix."
- **FilterPanel** (no fields selected, stats visible): "Select fields in the Analysis panel to show filter histograms." with a "Hide Statistics" button.
- **FilterPanel** (stats off, no numeric fields): "No numeric fields available in this dataset."

### Word Frequency Log Scale

Log mode uses `Math.log10(count)` instead of `log10(pct + 1)`. Counts span orders of magnitude (5 to 500+), percentages don't — so log now shows dramatic visual difference.

### Search Area Empty & Error States

When the search area (`VideoGrid.svelte`) has no results or an API error, it shows:
1. A centered message (error in red, empty in dim text)
2. The BirdsEye logo watermark at 2/3 width, 8% opacity, matching the text color

**Rationale:** Raw "API error 400 Bad Request" is not helpful. The user needs to
understand what went wrong and what to do about it.

**Error message improvement:** `checkedJson()` in `api.js` now reads the JSON body
from error responses before throwing. The server already returns structured
`{"error": "Vector index 'clip' not available. Available: []"}` responses — the
frontend was just throwing away the body and showing the HTTP status line instead.

**Edge cases and their messages:**
- Hull search on dataset without CLIP → "Vector index 'clip' not available. Available: []"
- Semantic search with no query → "Type a description for semantic search"
- Hull search with no selection → "Select videos first, then use Hull mode"
- No matching results → "No videos match your search."
- Unknown dataset → "Unknown dataset: xyz"

The logo watermark uses the same CSS mask-image technique as the header logo but
inherits `currentColor` from the text (dim gray), not the accent color.

### Upcoming: Download Selected Samples

**Feature:** A "Download Selected" button that zips up sample directories for manually
selected videos and serves as a browser download.

**Backend:** `POST /api/download` — accepts `{dataset, video_names: [...]}`. Hard cap
at 50 samples (safety limit). Creates a temp zip of sample directories with flat
structure (no shard nesting): `dataset_videoname/thumb_middle.jpg`, etc. Streams back
with `Content-Disposition: attachment; filename="samples.zip"`.

**Frontend:**
- Download button in toolbar (near Export): `<iconify-icon icon="mdi:download">`.
  Shows count: "Download (3)". Only enabled when `selectedVideos.size > 0`.
- Per-sample download button in detail panel: downloads just that one sample.
- NO "download all results" option — only manually selected samples.

**Helper:** Pure function `zip_sample_dirs(sample_paths) -> bytes` in a utility module.
The endpoint calls it and streams the result. Zips the entire sample directory as-is.

### Upcoming: Multi-Dataset UI

Currently one dataset visible at a time via dropdown. Future enhancement:
- Filter panel has dataset checkboxes (one or multiple selected)
- Re-fetch metadataStats/histograms/fieldInfo on dataset selection change
- fieldInfo becomes dataset-scoped (different datasets may have different fields)
- API: `/api/field_info?dataset=pexels` returns fields for that specific dataset
