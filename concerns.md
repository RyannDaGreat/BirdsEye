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

## 2026-03-02 — Reload Indicator Was Fundamentally Broken

### Bug 1: Reload never updated server data
- The reload button called `window.location.reload()` which just refreshed the page
- But the server still had OLD data in memory from boot time
- The `/api/reload/<dataset>` endpoint existed and correctly re-reads cache from disk, but **was never called**
- **Root cause**: The ReloadIndicator was designed to detect changes (via `/api/status` polling) but its "reload" action was a page refresh, not a server-side cache reload. The two concepts (detect change vs apply change) were never connected.

### Bug 2: Status diff showed nonsensical numbers (69927 → 0)
- `initialCounts` captured on first poll might have keys that don't exist in later polls (or vice versa)
- `buildChangeDetails()` iterated over `currentCounts` and compared to `initialCounts[key] || 0` — the `|| 0` fallback created phantom diffs for keys that didn't exist initially
- **Fix**: Only compare keys present in BOTH snapshots. Skip keys missing from either.

### Fix
- Reload button now calls `/api/reload/<dataset>` first, waits for response, then dispatches a `reload` event
- App.svelte handles the event by re-fetching all stores (metadata, histograms, field info, models, favorites) and re-running the search
- No full page reload needed — UI state (selections, filters, scroll position) is preserved
- **Lesson**: Detection and action must be connected. Polling for changes is useless if the "fix" button doesn't actually apply the fix.

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

## 2026-03-02 — Statistics Panel Polish Session

### Mistakes

**Checkbox widgets instead of small icons**: User asked for "checkmarks" on field bars. I implemented `mdi:checkbox-marked` / `mdi:checkbox-blank-outline` which looked terrible — wrong theme, not centered, too visually heavy. User clarified they wanted small iconify icons (`mdi:check` / `mdi:close`) in the accent color theme. Lesson: "checkmark" ≠ "checkbox widget."

**Field bars stretching full width**: Made field bars `display: flex; width: 100%` which stretched them across the entire column. User wanted them only as wide as the longest field. Fix: `width: max-content; max-width: 100%` on the field-list container.

**Active border too aggressive**: Solid `var(--accent)` border on active field bars was visually overwhelming in a list of many fields. User requested 50% transparency. Fix: `border-color: rgba(74, 158, 255, 0.4)`.

**Filter histograms reappearing when stats closed**: Original logic: `$showStats ? allFields.filter(...) : allFields` — closing stats brought back ALL histograms. This defeated the entire purpose of field toggling (decluttering filters). The user's intent: `activeFields` is a persistent selection that controls visibility everywhere, regardless of whether the stats panel is open. Fix: always filter by `activeFields` when it has been initialized.

**Word frequency log mode barely visible**: `log10(pct + 1)` where pct is ~0.01–0.05 produces `log10(1.01)–log10(1.05)` ≈ 0.004–0.021 — essentially linear for small values. Users expected dramatic compression like in SPLOM (which operates on raw values spanning orders of magnitude). Fix: use `Math.log10(count)` which uses actual occurrence counts (5 to 500+) that DO span orders of magnitude.

**SPLOM not reacting to external hover**: Implemented `hoveredFields` store but SPLOM only SET it on its own hover — it didn't SUBSCRIBE to external changes. Field bar and histogram hover didn't highlight SPLOM rows/columns. Fix: reactive block watches `$hoveredFields`, translates field keys to row/col indices, renders crosshair. `localHover` flag prevents infinite loop with SPLOM's own hover events.

### Decisions

- **Separators must touch edges**: User aesthetic preference — all lines/separators must touch adjacent borders with zero gaps. Achieved via negative margins to break out of column padding.
- **Field tooltips follow mouse**: Popover tooltips on field bars blocked adjacent fields. Replaced with mouse-following `.mouse-tip` div in the stats panel (detail panel still uses Popover).
- **Same-source comparisons disabled**: Results−Results, Dataset−Dataset, Selection−Selection are useless (zero differential). Bottom row disables whichever source the top row has selected.
- **Alpha-crop SPLOM canvas**: Eliminates wasted padding from generous label reserves (PAD_LEFT/RIGHT/TOP = 150px each). `findAlphaBounds()` scans for non-zero alpha pixels and crops to tight bounding box.

**Cross-component hover was not unified — major architectural mistake**: Initially implemented `hoveredFields` coupling separately in each parent component (StatsPanel wired mouseenter/mouseleave manually, DetailPanel had no coupling at all, FilterPanel used wrapper divs). User correctly identified this as wrong: "There should be one thing they all inherit from. One behavior, one helper, one unified function." The fix: moved ALL hoveredFields logic INTO `FieldBar.svelte` itself. Added `fieldKey` prop — any FieldBar with `fieldKey` set automatically participates in cross-component highlighting without the parent doing anything. This is the correct pattern: shared behavior belongs in the shared component, not duplicated across consumers. Same principle applies to any future component that participates in field highlighting.

**SPLOM crash on field toggle**: `hoverRow`/`hoverCol` became stale when fields were removed (indices pointing beyond the reduced array). Root cause: no bounds reset when the `fields` array changed reactively. Fix: reset hover indices when `n` changes, plus bounds checks in `compositeFrame`.

**Python `true` vs `True` crashed the entire UI**: Added `"dynamic": true` (JavaScript syntax) in Python server code. Python uses `True`. The `/api/field_info` endpoint threw `NameError`, returning 500. This cascaded: `fieldInfo` empty → `metadataStats` empty → no fields, no histograms, no sort options, "No numeric fields available" error. Switching datasets briefly masked it because browser-cached data persisted. Lesson: ALWAYS test server changes, and language-mixing bugs are the worst because they look syntactically correct in the wrong language.

**Mouse-tip tooltips used `position: absolute` instead of `position: fixed`**: Tooltips were positioned relative to parent containers, which meant they were clipped by `overflow: hidden` ancestors. The Popover component already solved this with `position: fixed` + `z-index: 99999` and appending to `document.body`. The mouse-tip should have used the same approach from the start. Fix: `.mouse-tip` now uses `position: fixed` with `z-index: var(--z-tooltip)`. All tooltip offset math simplified from parent-relative to viewport coords via shared `tipPos(e)` helper. The Popover's hardcoded `99999` was also replaced with `var(--z-tooltip)`.

**Magic number duplication between CSS and JS**: Initially defined tooltip offsets in both CSS vars (`--tip-offset-x/y`) and JS constants (`TIP_OFFSET_X/Y`). User correctly identified this as redundant. Since the offsets are only used in JS positioning, removed from CSS. Single source: `tipPos()` in format.js.

## 2026-03-02 — Dynamic Fields Treated as Second-Class Citizens

### Problem
Dynamic fields (like CLIP Score) were completely invisible in two critical places:
1. **FilterPanel** — no histogram, no ability to filter by score
2. **DetailPanel** — score not shown in field bars when viewing a video

### Root Cause — Three Breaks in the Chain
The architecture had a fundamental mismatch: `score` is computed per-query (not stored on disk), but the filter/histogram system was built around pre-computed fields with known min/max ranges from `metadataStats`.

1. **Server `compute_result_histograms()`**: Collected score values from results but **discarded them** — the histogram loop only iterated `metadata_stats.items()`, and score wasn't in `metadata_stats`.
2. **`availableFields($metadataStats)`**: FilterPanel derived its field list from `metadataStats` keys. Score never in `metadataStats` = never shown.
3. **`collectVideoFields(data)`**: Only checked `data.metadata` and `data.stats` objects, not top-level properties like `data.score`. And `onDetail()` called `fetchVideoInfo()` which discarded the clicked item's score entirely.

### Fix — Three Corresponding Changes
1. **Server**: After the main histogram loop, also emit histograms for fields found in results but NOT in `metadata_stats`, computing min/max from collected values.
2. **App.svelte**: After receiving result histograms, augment `$metadataStats` with any new fields from the histogram response. This makes `availableFields()` pick them up automatically.
3. **DetailPanel**: `onDetail()` now preserves `item.score` on the detail data. `collectVideoFields()` now checks top-level `data.score`.

### Lesson
Dynamic fields must not be second-class. The principle: **one field, one path through the system**. If a field exists, it appears in field bars, histograms, filters, SPLOM, sort, and detail — no exceptions. The only acceptable difference: dynamic fields get the ✦ marker and sort first.

### Consolidation — Normalization Instead of Special Cases
The initial fix added score-specific code in 7+ places. User correctly identified this as too much code for adding one field. The real fix: **normalize at the source**. `enrich_results()` now sweeps ALL top-level numeric values on result dicts into `stats` via a generic loop (not score-specific). This eliminated:
- `if "score" in r` in `compute_result_histograms()` — deleted
- `if key == "score"` in `get_sort_value()` — deleted
- `if (item.score !== undefined)` in `collectNumericFields()` — deleted
- `if (typeof data.score === 'number')` in `collectVideoFields()` — deleted
- `if (key === 'score')` in `getNestedValue()` — deleted
- `if (item.score !== undefined) info.score = item.score` in `onDetail()` — replaced with generic stats merge
- `item.score` in `VideoCard.svelte` — replaced with `getNestedValue(item, 'score')`

One 4-line normalization loop replaced 7 special cases. Any future dynamic field (e.g., aesthetic_score, motion_score) gets the same treatment automatically.

**Key distinction**: "dynamic" means computed at query time, not stored on disk. Fields from processors/datasets are crystallized to disk during processing and are NOT dynamic. Only fields that change based on the search query or user action (like CLIP similarity score) are dynamic. The `dynamic: True` flag in `/api/field_info` is set explicitly per field — it's NOT automatic from the normalization sweep.

### The Ratchet Problem — Dynamic Field Histogram X-Axis
**Problem**: Dynamic fields have no dataset-wide min/max. Initial approach derived min/max from current results and used that for the histogram x-axis. When the user filtered to a narrow range, the next search returned narrower results, which updated the x-axis to a narrower range, which pushed the filter handles back to the edges — making it impossible to widen the filter. A one-way ratchet.

**Fix**: Dynamic fields declare their theoretical range in `field_info` (e.g., `"range": [0, 1]` for cosine similarity). The server uses this declared range for histogram binning (`DYNAMIC_FIELD_RANGES`, derived from `SERVER_FIELDS`). The histogram x-axis is always 0–1 for score, regardless of what the current results contain. The frontend augments `metadataStats` with the histogram's stable lo/hi, and only ever expands (never shrinks) the range.

**Also fixed**: Duplicate score in sort dropdown (hardcoded `<option value="score">` AND `availableFields()` both included it). Removed the hardcoded option — score now comes through `dynamicFields` like every other field. Also: detail panel field order wasn't sorted — `collectVideoFields()` now applies `sortFieldKeys()` so dynamic fields appear first.

### SPLOM Font Size
Changed from hardcoded `9px` to named constant `LABEL_FONT_SIZE = 14` (1.5x increase per user request).

## 2026-03-02 — CLIP/Score Knowledge Hardcoded Outside Plugin System

### Problem — Major Architectural Violation
Score field metadata ("CLIP Score", description, range [0,1], dynamic flag) was hardcoded in `SERVER_FIELDS` in `server/app.py`. This violates the plugin architecture: CLIP knowledge should come from the CLIP processor plugin, not be baked into the server. The server should be model-agnostic. If a second embedding model (e.g., SigLIP, DINOv2) is added as a processor plugin, it should declare its own score field and everything should just work — but it couldn't, because the server hardcoded "CLIP Score".

**14 places** had CLIP/score-specific code outside the plugin:
- `SERVER_FIELDS` in app.py (label, description, range, dynamic flag)
- `DYNAMIC_FIELD_RANGES` derived from SERVER_FIELDS
- `field_info()` merging SERVER_FIELDS into response
- Fuzzy search hardcoding `"clip"` index + encoder
- VideoCard.svelte hardcoding `'score'` lookup + `* 100`
- `FIELD_ORDER` in fields.js including `'clip_std'` and `'score'`
- Various `index="clip"` defaults
- Error messages mentioning "CLIP" by name

### Fix — Score Field Declared by Plugin
1. Added `score_field` to `embedding_space` in `ClipProcessor`:
   ```python
   "score_field": {"key": "score", "label": "CLIP Score", "description": "...", "dtype": "float", "dynamic": True, "range": [0, 1]}
   ```
2. Updated `collect_field_info()` in `__init__.py` to also collect score fields from `embedding_space.score_field`
3. Removed `SERVER_FIELDS` from app.py entirely
4. `DYNAMIC_FIELD_RANGES` now derived from processor plugins
5. `field_info()` uses only plugin-provided fields (no server-hardcoded ones)

### Remaining Hardcoded Items (acceptable or deferred)
- `get_vector_index()` default `prefix="clip"` — acceptable default, overridden by dynamic mode selection
- `clip_search()` function name — code is actually generic FAISS search, name is historical
- `searchClip` in api.js — calls the generic `/api/search/clip` endpoint
- VideoCard.svelte `'score'` lookup — this is the field key, not CLIP-specific
- `FIELD_ORDER` including `'score'` and `'clip_std'` — presentation preference, not logic
- Error messages mentioning "CLIP" — should be made dynamic in future (use model name from plugin)

### Lesson
Score field metadata belongs in the processor that produces the embeddings, not in the server. The plugin contract's `embedding_space` is the right place because the processor knows what kind of similarity its embeddings compute and what range the scores will have.

## 2026-03-02 — SigLIP Plugin Integration (Vidi Research → SigLIP)

### Research: Vidi vs SigLIP
- User asked to integrate the ByteDance Vidi model (https://github.com/bytedance/vidi)
- **Key finding**: Vidi is a GENERATIVE video-language model (outputs text timestamps/descriptions), NOT an embedding model. It does NOT produce vectors suitable for similarity search.
- **However**: Vidi's vision tower is `google/siglip-so400m-patch14-384` — a standard contrastive vision-language model (like CLIP but better). SigLIP IS an embedding model.
- **Decision**: Use SigLIP directly instead of the full Vidi model. Same embeddings, simpler integration, no wasted parameters from the LLM backbone. SigLIP has both vision and text towers (1152-dim shared space).

### Implementation
- Added `sentencepiece>=0.1.99` and `protobuf>=3.20` to pyproject.toml (required by SigLIP tokenizer)
- Extracted `mean_pairwise_cosine_distance()` from clip.py to base.py (shared by all embedding processors)
- Created `preprocess/processors/siglip.py` following exact CLIP processor pattern:
  - `SiglipProcessor(Processor)` with name="siglip", human_name="SigLIP Embeddings"
  - 4 artifacts: siglip_embedding.npy, siglip_first.npy, siglip_last.npy, siglip_std.json
  - 1 field: siglip_std (diversity metric)
  - 1 dynamic field: siglip_score (via embedding_space.score_field)
  - embedding_space with prefix="siglip", dim=1152
  - GPU subprocess pattern with _batched_siglip_forward()
  - encode_text() with lazy-loaded singleton
  - Fire CLI with main + gpu_worker subcommands
- Auto-discovery validates no collisions: 6 processors loaded with zero conflicts
- Processed 750 pexels samples through SigLIP on 8 GPUs (50 samples in 24s per batch)
- Cache files created: siglip_embeddings.npz (750x1152), siglip_index.faiss, siglip_names.json

### Tests Created
- `tests/test_siglip_processor.py` — 24 tests (21 non-GPU + 3 GPU):
  - Shared math function tests (mean_pairwise_cosine_distance with various dims)
  - Class attribute validation (name, artifacts, fields, embedding_space, score_field, aggregation)
  - Collision tests (no artifact/field/prefix/score_key collision with CLIP)
  - needs_processing tests (empty/complete/partial dirs)
  - encode_text shape, normalization, semantic similarity tests
- `tests/test_multi_embedding.py` — 17 tests (13 non-GPU + 4 GPU):
  - Processor coexistence (both discovered, no collisions, both text encoders found)
  - Dynamic field ranges for both models
  - FAISS search with both 512-dim (CLIP) and 1152-dim (SigLIP) mock indices
  - Similar videos rank higher than dissimilar (cluster test)
  - Score normalization into stats dict
  - Both models agree on semantic similarity (cat/kitten > cat/car)
- Full test suite: 55 passed, 7 skipped, 0 failures

### End-to-end verification
- SigLIP text search for "sunset over ocean" correctly returns sunset/ocean videos in top results
- Server loads both clip and siglip vector indices simultaneously
- Both text encoders available via collect_text_encoders()

### SigLIP characteristics vs CLIP
- SigLIP scores are numerically lower (0.13 range) vs CLIP (0.29 range) for the same queries
- This is expected: SigLIP uses sigmoid loss, CLIP uses softmax — different score scales
- Both use [0,1] range declaration for histogram binning
- SigLIP model is ~3.6GB (vs CLIP ~600MB) — loads slower, needs more GPU memory

## 2026-03-02: GVE-3B integration fixes

### HuggingFace cache race condition
- **Bug**: 8 GPU workers calling `from_pretrained("Alibaba-NLP/GVE-3B")` simultaneously race on HuggingFace's cache lock. Some workers fail with `OSError: does not appear to have a file named model-*.safetensors`.
- **Fix**: `snapshot_download()` in `gpu_worker()` resolves to local path, passed to workers so `from_pretrained()` loads from disk without hub resolution.

### CUDA fork error
- **Bug**: `set_start_method("spawn")` silently failed when already set, causing CUDA fork errors in GPU workers.
- **Fix**: Changed to `set_start_method("spawn", force=True)` in `distribute_across_gpus()`.

### GVE OOM on 15GB GPUs
- **Bug**: Qwen2.5-VL processes images at variable resolution — large thumbnails create many vision tokens, exceeding 15GB VRAM even for a single image.
- **Fix**: Added `GVE_MAX_PIXELS = 384*384` cap in `_load_image()`, resizing thumbnails before GVE processing. Also `FORWARD_BATCH=1` and `torch.cuda.empty_cache()` between forward passes.

### Text encoders hardcoded to cuda:0
- **Bug**: All three text encoders (CLIP, SigLIP, GVE) hardcoded `device = "cuda:0"`. When the server tried to load the 3B GVE model, it OOMed on a GPU already occupied by other models.
- **Fix**: All three now use `rp.select_torch_device(reserve=True)` — picks GPU with most free VRAM, uses filelock so models don't clobber each other.

### FileExistsError in ensure_sample_dir
- **Bug**: Parallel workers in `compress.py` race on creating `video.mp4` hardlink. `os.path.exists()` check passes for both, first `os.link()` succeeds, second gets `FileExistsError`. The `except OSError` fallback to `os.symlink()` also fails.
- **Fix**: Added `FileExistsError` handling (pass — the link exists, which is what we wanted).

### Reload button spinner
- Added spinning animation to the reload dataset button while server cache is reloading. Button stays visible during reload with a CSS spin animation so the user knows something is happening.

### Search bar debounce
- Unified debounce to 1 second (`DEBOUNCE_MS = 1000`) for all search modes. Previously 500ms for embedding models, 150ms for fuzzy. Enter key still fires immediately.

---

## 2026-03-02: Search Status Updates, Dynamic Score Fields, UI Polish

### Bug: clip_search() hardcoded "score" key
- **Root cause**: `clip_search()` and `convex_hull_search()` in `server/search.py` always returned `{"score": float}` regardless of which embedding model was used. Processors declared different score keys (`siglip_score`, `gve_score`) in `embedding_space.score_field.key`, but the search functions ignored them.
- **Fix**: Added `score_key` parameter to both functions (default `"score"` for backward compat). Server builds `SCORE_KEYS` mapping from plugin declarations at startup. All search endpoints pass the correct score key.
- **Also fixed**: Fuzzy search hardcoded `"clip"` as the embedding model for similarity scoring. Now uses the first available model from `text_encoders` dict — no model is special-cased.
- **Also fixed**: Removed `has_clip` from `/api/datasets` response (was the last hardcoded "clip" reference in main server code; frontend never used it).

### Feature: SSE search status streaming
- **Problem**: First-time embedding searches could hang 30-60s (especially GVE-3B) with no progress feedback.
- **Solution**: Created `server/status.py` with thread-local callback mechanism. Processors call `set_status()` during `_ensure_text_encoder()`. The `/api/search/clip` endpoint streams SSE events when `Accept: text/event-stream` is requested. Frontend reads the stream via `searchClipStreaming()`, updating `searchStatus` store shown in `VideoGrid.svelte`.
- **Backward compat**: Without `Accept: text/event-stream`, endpoint returns normal JSON.

### UI: Frames preview collapsed by default
- Changed ingest processor's Frames preview_section priority from 20 to 40. `SectionRenderer` collapses sections with priority > 30.

### UI: Caption moved above preview sections
- Caption PreviewSection now appears directly after Fields, before plugin-declared preview sections. Previously was after all preview sections.

## 2026-03-03 — Export Modal Overhaul + Download Unification

### Export Modal Overhaul
- **Problem**: Export modal was too simple — just dumped video names into a textarea with no options.
- **Solution**: Full rewrite of ExportModal.svelte. Four-band layout (header, controls, content, footer). Fixed 85vh × 80vw modal. Two content modes (Names / Paths), two format modes (Lines / JSON). Artifact dropdown in Paths mode populated from processor plugin declarations via `$fieldInfo` — no hardcoding of artifact filenames. Spinner overlay while loading. Icons on all buttons.
- **Design rationale**: Users need to export different things — sometimes just video names for scripting, sometimes full paths for batch processing, sometimes specific artifact paths. The artifact dropdown is plugin-driven so new processors automatically appear without UI changes.

### Server: paths added to export endpoints
- `/api/export/names` now returns `{names, paths, total}` instead of just `{names, total}`. Paths computed via `resolve_sample_path()`.
- New `POST /api/export/resolve` endpoint — takes `{dataset, video_names}`, returns sorted `{names, paths}`. Used by "Export Selected" to get paths without re-running the full search.
- **Why two endpoints**: "Export All" runs the full search pipeline (filters, sort, etc.) to get names+paths. "Export Selected" only needs to resolve already-known names to paths — no search needed.

### Download Button Unification
- **Problem**: Download button code was duplicated — StatusBar had inline download with Popover and downloadStatus, ExportModal needed the same behavior. User explicitly requested: "inherit the download button and all its behaviors so when we modify one download button, we modify them all."
- **Solution**: Created `DownloadButton.svelte` widget — self-contained component with props (dataset, videoNames, artifact, compact). Fetches size estimate via `POST /api/download/size`, shows human-readable file size. Shows spinner + status while downloading. Used by both StatusBar and ExportModal.
- **Artifact-aware downloads**: `POST /api/download` now accepts optional `artifact` parameter. When null, zips full sample directories. When set (e.g., "video.mp4"), zips only that file per sample, flat-named (e.g., `pexels_19012581.mp4`). This avoids the degenerate case of downloading folders where every subfolder contains a single identically-named file.
- **Size estimation**: `POST /api/download/size` returns `{total_bytes, file_count}` so users know what they're getting into before clicking download.
- `downloadSamples()` in api.js now accepts optional artifact and statusStore params. Each DownloadButton instance gets its own writable store so multiple buttons don't interfere.

### Removed onDownload from App.svelte
- StatusBar no longer dispatches 'download' event. DownloadButton is self-contained — it calls `downloadSamples` directly. App.svelte no longer needs an `onDownload` handler or a `downloadSamples` import. Cleaner separation of concerns.

### Bug: `__pycache__` detected as dataset
- **Problem**: Dataset loader scans `datasets/` with `os.listdir` and tries every subdirectory. Python's `__pycache__/` passed the `os.path.isdir` check, hit the "no manifest" skip message: `Skipping dataset '__pycache__': no manifest at ...`. Harmless but ugly.
- **Fix**: Added `if name.startswith('.') or name.startswith('__'): continue` before the `isdir` check in `create_app()`. Filters out `__pycache__` and hidden dirs before they're ever considered as datasets.
