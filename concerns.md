# BirdsEye — Concerns & Progress Log

## 2026-02-26 — Project Init

### Progress
- Created directory structure and git repo
- Created manifest (claude_instructions.md) with full requirements
- Created TODO list with 8 tasks

### Requirements Captured
- User wants working website ready by morning
- Must test with VLM verification for CLIP search results
- Must use all 8 GPUs for embedding computation (batch swarm)
- Regular git commits required
- FZF extended mode (word-boundary) fuzzy search
- Clean UI is very important
- Dataset format must be uniform/extensible for future datasets
- Export video names as copyable text
- Selection + convex hull search in embedding space

### Risks
- 81,766 videos to generate thumbnails for — need fast parallel processing
- 863MB JSON to parse — memory concerns, use streaming if needed
- CLIP embeddings for 81k images across 8 GPUs — batch swarm planned
- Thumbnail generation depends on video files existing at cleancode_pexels_path

## 2026-02-26 12:30 — Core System Working

### Progress
- Distilled metadata: 81,766 entries extracted, 0 duplicates
- Server running on port 8899 with all 3 search modes working
- CLIP embeddings computed for ~2,475 videos (first batch)
- VLM-verified CLIP search results:
  - "sunset over ocean" → beach sunset (12896646), ocean sunset aerial (19178208) ✓
  - "people dancing" → indigenous dance (2927946) ✓
  - Hull search from 2 sunset videos → 3 more sunset videos ✓
- Fuzzy search tested: "sunset ocean", "cat|dog", "'blue sky' mountain", "car !red" — all work
- Thumbnail generation at ~100/min with 64 workers (S3 backend is bottleneck)
  - Currently 3,500/81,766 done (~4.2%)
  - ETA: ~13 hours for full set

### Issues Found & Fixed
1. NoneType caption crash: some entries have None captions → fixed with `.get() or ""`
2. CLIP `get_image_features()` returns `BaseModelOutputWithPooling` in newer transformers
   → Fixed: use `model.vision_model()` + `model.visual_projection()` explicitly
3. S3 (FUSE) storage has high per-request latency → 64 workers balances throughput vs contention

### Architecture Decision
- Thumbnails generate in background while server is usable
- CLIP embeddings can be recomputed incrementally as more thumbnails appear
- Server auto-discovers datasets on startup

## 2026-02-26 13:05 — VLM Verification Complete

### CLIP Search VLM Verification (4 queries, 2475 videos indexed)
| Query | Top Video | Score | VLM Assessment |
|-------|-----------|-------|----------------|
| "cat sitting" | 14458880 | 0.261 | PASS — ginger tabby cat sitting indoors |
| "city skyline night" | 3052162 | 0.291 | PASS — dark landscape with city lights at night |
| "forest waterfall" | 12009016 | 0.301 | PASS — multi-tiered waterfall in lush green forest |
| "person running" | 12530557 | 0.326 | PASS — person on outdoor path (walking/light jog) |

All 4 queries return visually relevant results. CLIP search is working correctly.

### Fuzzy Search Verification
- "sunset ocean" → 3 results, all about coastal/ocean sunsets ✓
- "cat|dog" → OR search works, returns animal-related results ✓
- "'blue sky' mountain" → exact phrase + word match works ✓
- "car !red" → exclusion works ✓

## 2026-02-28 — Ingest Performance Bulldogging

### Target: 10 vid/s throughput for ingest processor
### Hardware: 96 cores, 369GB RAM, 16x Tesla T4 (CUDA 11.8, driver 580.65.06)

### CPU Decode Results (200 videos, mean=32MB)

| Approach | Best vid/s | Workers |
|----------|-----------|---------|
| **PyAV+cv2** | **3.3** | **w=16** |
| decord2+cv2 | 3.0 | w=16 |
| ffmpeg GPU subprocess | 2.6 | w=16 |
| decord2+PIL | 1.8 | w=32 |
| cv2-only | 0.9 | w=32 |

**CPU ceiling: 3.3 vid/s — cannot be improved without GPU acceleration.**

### GPU Decode Exploration

#### PyNvVideoCodec v2.1.0
- pip installable, has `get_batch_frames_by_index()` for selective frames
- Single video: ~700ms for 25 frames from 1440p
- **BUG: FPE crash after ~4 videos sequentially** (decoder cache lifecycle bug)
- **BUG: multiprocessing can't pickle `_PyNvVideoCodec` module** (dynamic import issue)
- Likely CUDA 11.8 incompatibility with wheel built for CUDA 12.x/13.x

#### decord2 GPU — ATTEMPTING BUILD FROM SOURCE
- PyPI wheel is CPU-only (confirmed)
- Building from source with `-DUSE_CUDA=ON` to test GPU decode

### Code Changes
- `video_utils.py`: replaced decord2+PIL with PyAV+cv2
- `ingest.py`: updated to use new cv2 functions, DEFAULT_WORKERS=16
- `pyproject.toml`: added pynvvideocodec, av

## 2026-02-28 12:00 — v2 Server/Frontend Rewrite

### Context
Previous Claude session crashed while investigating v1 cruft in frontend. The server and frontend had never been updated for v2 architecture — still using v1 paths (embeddings/, thumbnails/, hq_prefix, clip_stds as separate file).

### Changes Made

1. **Created `preprocess/aggregator.py`**
   - Scans `datasets/<name>/samples/` via os.walk
   - Reads per-sample artifacts: metadata.json, clip_std.json, flow_stats.json, phash_stats.json, clip_embedding.npy
   - Builds cache/ directory: clip_embeddings.npz, clip_index.faiss, video_names.json, video_metadata.json, video_stats.json, cache_manifest.json
   - Incremental: reads existing cache_manifest.json, only processes new samples
   - Fire CLI, tqdm progress bars

2. **Rewrote `server/app.py` for v2**
   - `load_dataset()` reads from `datasets/<name>/cache/` (was: embeddings/, flat dataset dir)
   - Thumbnail serving with shard routing: `/thumbnails/<dataset>/<video_name>/<file>` → computes shard, serves from `samples/<shard>/<sample_id>/<file>`
   - All thumb URLs use `thumb_` prefix (was: `middle.jpg`, now: `thumb_middle.jpg`)
   - Removed `clip_stds` as separate entity — merged into `video_stats`
   - Removed `thumb_base` and `embed_base` variables (v1 concepts)
   - Added `/api/reload/<dataset>` for hot-reload without server restart
   - `video_info` endpoint uses shard routing, `thumb_` prefix

3. **Updated `server/search.py`**
   - Removed `merge_video_stats()` (clip_stds now in video_stats)
   - `all_numeric_values()` takes 2 params (metadata, stats) instead of 3
   - `apply_filters()` signature simplified (no separate clip_stds param)

4. **Updated frontend for v2**
   - Removed `thumbQuality` store and all references
   - Removed `SettingsPanel` (only contained quality toggle)
   - `VideoCard.svelte`: `thumb_` prefix, removed `hq_`/`small` logic
   - `SearchHeader.svelte`: removed settings button
   - `url.js`: removed thumbQuality from URL state sync

5. **Updated README.md**
   - Complete rewrite covering: processing pipeline, server startup, API endpoints, live data updates, plugin architecture, extensibility, multi-machine safety

### API Verification (all passing)
- `/api/datasets` → 81766 videos, has_metadata=true
- `/api/metadata_stats/pexels` → 10 numeric fields with min/max
- `/api/histograms/pexels` → 10 fields with bin counts
- `/api/field_info` → 17 fields from all plugins
- `/api/search/fuzzy?q=sunset` → 3 results with thumb_middle.jpg URLs
- `/api/video_info/pexels/9466189` → full metadata, stats, thumbnails, video_url
- `/api/status/pexels` → entries=81766, metadata=1000, stats=1000
- Thumbnail shard routing: 200 OK for processed videos, 404 for unprocessed

### Current State
- Overnight run active: compress+ingest+phash, batch 2 starting (~1662 samples done)
- Server reads from cache/ (aggregated from 1662 samples)
- Frontend builds cleanly, all v1 cruft removed
- No CLIP embeddings yet (clip processor hasn't run)

### Risks
- aggregator.py NFS I/O is slow (~17 it/s for metadata reads)
- Frontend shows "failed to load" for unprocessed videos (expected — they have no thumbnails)

## 2026-02-28 13:00 — Three Features: Priority Sort, Plugin-Driven Aggregator, Auto-Aggregation

### Progress
All three features implemented and tested:

1. **Prerequisite priority sorting** (`process_all.py`)
   - After shuffle, stable-sort by # of processors whose dependencies are already satisfied (descending)
   - Videos with all deps ready get processed first, maximizing throughput
   - Tier breakdown printed at startup (e.g., "Tier 5/5 (all deps ready): 2 videos")
   - Pure functions: `count_satisfied_deps()`, `format_tier_breakdown()`, `priority_sort()`
   - Tested on real data: 3,452 samples, correct tier distribution

2. **Plugin-driven aggregator** (complete rewrite of `aggregator.py`)
   - Each processor declares `aggregation` rules in its class definition
   - Two generic types: `json_dict` (merge JSON → keyed dict), `vector_index` (build FAISS)
   - Aggregator reads rules from plugins — zero hardcoded file paths
   - Server loads vector indices generically (scans for `*_index.faiss`)
   - CLIP search endpoint accepts `index` parameter for future extensibility
   - Collision validation extended to check vector_index prefix uniqueness
   - New helper: `collect_aggregation_rules()` in `__init__.py`

3. **Auto-aggregation per batch** (`process_all.py`)
   - After each batch completes, runs aggregator automatically
   - `--auto_aggregate` flag, default True
   - Server can pick up new data incrementally via `/api/reload/<dataset>`

### Changes Made
- `preprocess/processors/base.py`: added `aggregation` class attribute
- `preprocess/processors/ingest.py`: added json_dict → video_metadata.json
- `preprocess/processors/clip.py`: added json_dict → video_stats.json, vector_index "clip" 512-dim
- `preprocess/processors/phash.py`: added json_dict → video_stats.json
- `preprocess/processors/raft_flow.py`: added json_dict → video_stats.json
- `preprocess/processors/__init__.py`: added `collect_aggregation_rules()`, vector_index prefix collision check
- `preprocess/aggregator.py`: complete rewrite — plugin-driven, generic vector indexing
- `preprocess/process_all.py`: added priority sorting + auto-aggregation + auto_aggregate flag
- `server/app.py`: generic vector index loading, `get_vector_index()` helper, `index` param on search endpoints
- `README.md`: complete rewrite with all API endpoints, plugin-driven aggregation docs
- `claude_instructions.md`: updated aggregator section, process_all.py logic, API endpoint table

### API Verification (all passing after refactor)
- `/api/datasets` → has_clip=false (no CLIP yet), vector_indices=[]
- `/api/status/pexels` → entries=81766, metadata=2557, stats=2967
- `/api/search/fuzzy?q=sunset` → 3 results with metadata+stats enrichment
- `/api/search/clip` → correctly reports "Vector index 'clip' not available"
- `/api/field_info` → 17 fields, 4 image artifacts, 13 data artifacts
- `/api/histograms/pexels` → 10 histogram fields
- `/api/video_info/pexels/9466189` → full metadata + phash stats
- `/api/reload/pexels` → hot-reload works, returns updated counts

### Current State
- 3,452 samples processed (up from ~1,662 at last check)
- 2,557 have metadata, 2,967 have stats, 0 have CLIP embeddings
- Processing overnight run likely still active on another terminal
- Server running on port 8899 with all APIs verified

## 2026-02-28 14:00 — Frontend Fixes (6 changes)

### Progress
Six frontend improvements implemented from user feedback:

1. **Float/int dtype in plugin fields** — Each processor field now declares `dtype: "int"` or `"float"`. Propagates through `/api/field_info` to frontend. Integer fields (width, height, num_frames) use step=1. Float fields (clip_std, phash_*, flow_*) scale step by range. Backend: all 4 processors + server score field updated. Frontend: `fields.js` reads dtype from field_info.

2. **Sample count in filter header** — Each histogram filter shows `label (count)` where count = number of samples that have that field. Added `count` to `compute_metadata_stats()` return value. Frontend: HistogramFilter receives and displays count prop.

3. **Sort excludes missing values** — When sorting by a numeric field, `sortResults()` now filters out items that lack a value. Prevents undefined values from cluttering sorted results.

4. **Has-thumbnail toggle** — Button in filter toolbar (right of Log Y) with `mdi:image-check` icon. When enabled, hides videos whose thumbnails failed to load. Tracks load/error via `thumbnailStatus` store. VideoCard reports status on img load/error. VideoGrid filters `currentResults` by thumbnail status.

5. **Min/max handle swap** — When dragging the min handle past the max (or vice versa), handles implicitly swap roles. Ensures min is always <= max during drag.

6. **Reload indicator moved to header** — Was fixed bottom-right, now renders inline in SearchHeader between title and dataset selector. Uses Popover tooltip. Pulsing animation when new data detected.

### Changes Made
- `preprocess/processors/ingest.py`: added dtype to all 6 fields
- `preprocess/processors/clip.py`: added dtype to clip_std
- `preprocess/processors/phash.py`: added dtype to all 4 fields
- `preprocess/processors/raft_flow.py`: added dtype to all 5 fields
- `preprocess/processors/base.py`: updated docstring for dtype
- `server/app.py`: count in compute_metadata_stats, dtype on score field
- `frontend/src/lib/fields.js`: fieldDtype(), fieldStep() uses dtype, availableFields includes count+dtype
- `frontend/src/lib/sort.js`: sortResults filters out undefined values
- `frontend/src/lib/stores.js`: added requireThumbnail, thumbnailStatus stores
- `frontend/src/components/widgets/HistogramFilter.svelte`: count prop, handle swap, smart round()
- `frontend/src/components/FilterPanel.svelte`: passes count, has-thumbnail toggle button
- `frontend/src/components/VideoCard.svelte`: reports thumbnail load/error to store
- `frontend/src/components/VideoGrid.svelte`: filters by thumbnail status
- `frontend/src/components/SearchHeader.svelte`: ReloadIndicator integrated
- `frontend/src/components/ReloadIndicator.svelte`: rewritten for inline header, Popover tooltip
- `frontend/src/App.svelte`: removed standalone ReloadIndicator
- `run.sh`: fixed stale v1 thumbnail count check, now reads cache_manifest
- `claude_instructions.md`: documented dtype, count, sort behavior, reload indicator, toggle

## 2026-02-28 15:00 — Reload Indicator Fix + UI Polish

### Bug Found & Fixed
- **ReloadIndicator was NEVER triggering** — `/api/status/<dataset>` returned in-memory counts (loaded once at startup). Since the server never re-reads data, the counts never changed, so the frontend always thought data was "up to date". Fix: status endpoint now reads `cache_manifest.json` fresh from disk each request. When aggregator runs and updates the manifest, the next poll detects the difference.

### UI Changes
- URL state now syncs `requireThumbnail` (`thumb=1`) and `logScale` (`logY=0`) toggles
- Detail panel metadata fields (duration, fps, etc.) now show Popover tooltips on hover, same as filter question marks
- Histogram grid column width adjusted per user feedback
- Min/max input boxes narrowed per user feedback

## 2026-03-01 — Bird's Eye Logo (4 iterations of mistakes)

### Mistake 1: Logo pushed UI elements down
- Made the logo a large inline element → pushed the header taller and displaced elements below
- **Lesson**: Large decorative elements should float, not participate in layout flow

### Mistake 2: Logo pushed off screen with position:absolute + right:100%
- Used `position: absolute; right: 100%` to float it left of the title → pushed it off the left edge of the viewport. Only half visible.
- **Lesson**: `right: 100%` positions relative to the parent's left edge, so it goes OUTSIDE the container

### Mistake 3: Logo invisible with height:0 + overflow:visible
- Tried `height: 0; overflow: visible` trick to prevent vertical push → logo completely disappeared
- **Root cause**: CSS `mask-image` requires actual element dimensions to render. A 0-height element has no area, so the mask produces nothing visible.
- **Lesson**: CSS mask-image needs real width AND height on the element. You cannot use height:0 tricks with masked elements.

### Mistake 4: Final working solution
- Placeholder wrapper `<span>` at text line-height (1.2em) for horizontal push only
- Absolutely positioned logo at 3.25em centered on the wrapper via `top: 50%; left: 50%; transform: translate(-50%, -50%)`
- **Lesson**: Separate layout participation (wrapper) from visual rendering (absolute positioned child). The wrapper is tiny for layout, the child is large for display.

## 2026-03-01 — Ghost Preview Section (raft_flow)

### Bug
- raft_flow processor declared a preview section for `flow_sprite.jpg` but never generates that file
- UI showed "failed to load flow_sprite.jpg" in the preview panel
- **Root cause**: Copy-paste from another processor's preview_sections without updating filenames
- **Fix**: Removed the phantom preview section. raft_flow produces only `flow_stats.json` (numeric data), no visual artifacts.
- **Lesson**: Never declare a preview section for an artifact you don't generate. Preview sections must correspond 1:1 to actual output files.

## 2026-03-01 — JS Code Quality Slip

### Issue
- `humanFilesize()` was written inline in a Svelte component without JSDoc, without being labeled as pure, without examples
- User caught it: "I think you're getting sloppy with the pure functions"
- **Root cause**: Treating JS as second-class to Python. The same functional programming standards apply to ALL languages in this project.
- **Fix**: Extracted to `format.js` as a proper pure function with JSDoc and examples
- **Lesson**: JS pure functions must follow the EXACT same standards as Python: labeled "Pure function" in docstring, have JSDoc with examples, live in shared modules — never inline in Svelte components.

## 2026-03-01 — Video Sync (Event-Based Approach Failed)

### Failed Approach: Event propagation
- Listen for play/pause/seeked on ALL videos, propagate to siblings
- Added reentrant guard flags to prevent infinite loops
- **Result**: Infinite feedback loops and flickering. Even with guards, `currentTime` assignment triggers `seeked` events asynchronously, which fire after the guard is released.
- **Why it fails**: Browser video events are async. Setting `video.currentTime = X` doesn't fire `seeked` synchronously — it fires later in the event loop. By then, the guard flag has been cleared, so the handler re-triggers. This is fundamentally unsolvable with event-based sync.

### Working Approach: Master-slave + requestAnimationFrame
- First video is master (has controls), all others are slaves (NO controls, NO event listeners)
- Master's play/pause events control slaves directly
- `requestAnimationFrame` loop continuously checks drift: if master-slave time difference > 100ms, snap slave to master
- This is the industry standard for professional video comparison tools (confirmed by 10-agent research frenzy)
- **Lesson**: Never use bidirectional event listeners for video sync. Always use unidirectional master-slave.

## 2026-03-01 — Bash Argument Parsing Fragility

### Bug
- `run.sh` accepted `--google google` silently — unknown args fell through to the port variable
- No validation of argument names or values
- **Fix**: Initially added bash validation, then recognized bash is fundamentally wrong for this. Refactored entirely to Python Fire.
- **Lesson**: Bash `$1`/`$2` parsing is fragile and unsafe. Use Python Fire for any non-trivial argument handling. Fire gives typed args, auto `--help`, validation, and error messages for free.

## 2026-03-01 — Raw Error Messages (Theory of Mind Violation)

### Bug
- API errors returned raw technical messages like "Vector index clip not available for dataset pexels"
- Users have no idea what "vector index" or "clip" means in this context
- `checkedJson()` in the frontend was throwing away the JSON body of error responses, showing only HTTP status text

### Fix (two-part)
1. **Frontend**: `checkedJson()` now reads JSON body from error responses, extracts `error` and `hint` fields, attaches `hint` to the Error object
2. **Server**: All error responses now return `{error: "technical message", hint: "layman explanation"}` where the hint is specific, dynamic (interpolates dataset name, available features), and written for someone who has never seen the codebase

### Lesson
- **Theory of Mind**: Every user-facing message must be written for a newcomer. Don't say "vector index" — say "image similarity search." Don't say "may not have been processed" when you KNOW it wasn't. Be specific, be dynamic, interpolate real values.
- This principle was elevated to HIGH PRIORITY at the top of the manifest.

## 2026-03-01 — "Export All" Was Broken Since Day One

### Bug
- "Export All" button exported only the current page of results (e.g., 50 out of 80,000 matches)
- `$currentResults` store contains only one page of paginated results
- The code: `exportText = $currentResults.map(r => r.video_name).join('\n')` — looks correct at a glance, but `$currentResults` is NOT "all results," it's "current page results"

### Root Cause
- During the code audit, this was identified as "B3 (export all endpoint)" and explicitly marked "not needed" and "not worth the code." This was WRONG — the feature was broken without it.
- **Lesson**: Before dismissing a bug fix as "not needed," verify the CURRENT behavior actually works. The audit assumed export worked correctly without the endpoint. It didn't.

### Fix (planned)
- New `/api/export/names` endpoint that runs the same search + filters server-side but returns only video names, no pagination, no enrichment
- Frontend calls this endpoint for "Export All" instead of reading `$currentResults`

## 2026-03-02 — Statistics Panel v1 Issues

### Scatterplot Matrix Issues (all fixed)
1. **Blurry rendering**: Canvas was set to CSS pixel dimensions, not physical pixel dimensions. On HiDPI displays (devicePixelRatio > 1), the canvas was upscaled by the browser, causing blur. Fix: `setupCanvas()` multiplies canvas dimensions by `devicePixelRatio` and scales the 2D context.
2. **Non-square cells**: Grid cells had no aspect constraint, so cells stretched to fill rectangular areas. Fix: `aspect-ratio: 1` on cells.
3. **Labels inside cells blocking data**: Field names were rendered as absolute-positioned elements inside each cell, overlapping the scatter dots. Fix: moved labels to a separate header row (top) and label column (left), outside the N×N cell grid entirely.
4. **Vertical unreadable labels**: Left-side labels were rotated 90° which was hard to read. Fix: labels are now horizontal text in a dedicated column.
5. **No interactivity**: Hovering showed nothing. Fix: mousemove handler computes Pearson correlation coefficient and shows it in a floating tooltip.

### Stats Panel Reactivity Bug
- **Root cause**: `getSourceItems()` was a function that accessed `$currentResults` and `$selectedVideos` inside its body. Svelte's reactive `$:` only tracks store references in the top-level expression, not inside called functions. So `$: sourceAItems = getSourceItems($statsSourceA)` only re-ran when `$statsSourceA` changed, never when results changed.
- **Fix**: Pass stores as explicit arguments: `getSourceItems(source, $currentResults, $selectedVideos)` so Svelte sees them as dependencies.
- **Lesson**: In Svelte, reactive statements must directly reference all stores they depend on in the expression itself. Function calls that access stores internally will NOT trigger reactivity.

### Word Frequency Issues (all fixed)
- Too few words (only 30), should show up to 80
- Not scrollable horizontally, should fill full width
- Labels not centered on bars

### Drag Handle Dot Indicators — Removed
- Added dot indicators to resize handles, then immediately removed at user request. They weren't needed.
- **Lesson**: Don't add visual affordances without user request. The resize cursor change on hover is sufficient.

## 2026-03-02 — Field Taxonomy Clarification

### Issue
- Glossary defined "Field" as "a named numeric value per video" — too narrow
- Caption is a field (you can sort by it) but it's not numeric
- "Dynamic" was initially classified as a field subtype, but it's actually a modifier orthogonal to numeric/string

### Resolution
- **Field** = any named per-video value (numeric or string)
- **Numeric Field** / **String Field** = the type axis
- **Dynamic** = the persistence axis (stored on disk vs computed on-the-fly)
- These are orthogonal: you can have a dynamic numeric field (CLIP Score) or a stored string field (caption)
- Updated glossary to reflect this 2×2 taxonomy
