"""
Flask backend for Searchable Pexels v2.

Serves the web UI and provides search API endpoints:
  - /api/search/fuzzy   — FZF extended-mode text search
  - /api/search/clip    — CLIP semantic image search
  - /api/search/hull    — Convex hull search from selected videos
  - /api/datasets       — List available datasets
  - /api/metadata_stats — Min/max ranges for filterable fields
  - /api/histograms     — Histogram bin counts for filter UI
  - /api/field_info     — Field descriptions from processor plugins
  - /api/config         — Shared constants (sprite grid dimensions)
  - /api/favorites      — GET/POST favorites per dataset

All data is read from datasets/<name>/cache/, built by preprocess/aggregator.py.
Thumbnails are served from datasets/<name>/samples/<shard>/<sample_id>/<file>.

Usage:
    uv run python server/app.py --port 8899
"""

import json
import os
import sys
import numpy as np
import fire
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Add parent to path for imports
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from server.search import fuzzy_search, clip_search, convex_hull_search, apply_filters, all_numeric_values, sort_results, paginate, bin_values, l2_normalize
from server.clip_encoder import encode_text
from preprocess.video_utils import sample_dir, save_json_atomic


# --- Global state loaded at startup ---
DATASETS = {}  # dataset_name → {entries, video_names, embeddings, faiss_index, ...}
FAVORITES = {}  # {dataset_name: [video_name, ...]}
FAVORITES_PATH = os.path.join(REPO_ROOT, "user_data", "favorites.json")


def collect_numeric_fields(*dicts):
    """
    Collect all numeric values per field from one or more {name: {field: value}} dicts.
    Pure function. Returns {field_name: [values]}.

    >>> collect_numeric_fields({"v1": {"width": 1920, "fps": 30}})
    {'width': [1920], 'fps': [30]}
    >>> collect_numeric_fields(None, {"v1": {"x": 1.0}})
    {'x': [1.0]}
    """
    fields = {}
    for d in dicts:
        if not d:
            continue
        for record in d.values():
            for k, v in record.items():
                if isinstance(v, (int, float)):
                    fields.setdefault(k, []).append(v)
    return fields


def compute_metadata_stats(video_metadata, video_stats=None):
    """
    Compute min/max/count for all numeric fields across all sources.

    Pure function.

    >>> compute_metadata_stats({"v1": {"width": 1920, "height": 1080, "fps": 30, "duration": 10}})
    {'duration': {'min': 10, 'max': 10, 'count': 1}, 'fps': {'min': 30, 'max': 30, 'count': 1}, 'height': {'min': 1080, 'max': 1080, 'count': 1}, 'width': {'min': 1920, 'max': 1920, 'count': 1}}
    """
    all_values = collect_numeric_fields(video_metadata, video_stats)
    stats = {}
    for key, vals in sorted(all_values.items()):
        if vals:
            stats[key] = {"min": min(vals), "max": max(vals), "count": len(vals)}
    return stats


def is_filter_key(key):
    """
    Check if a query parameter key is a filter key (min_* or max_*).

    Pure function.

    >>> is_filter_key("min_duration")
    True
    >>> is_filter_key("max_fps")
    True
    >>> is_filter_key("dataset")
    False
    """
    return key.startswith("min_") or key.startswith("max_")


def parse_filters(args):
    """
    Extract filter parameters from a dict-like object (Flask request.args or plain dict).
    Dynamically accepts any min_* or max_* parameter. Pure function.

    >>> parse_filters({"min_duration": "5", "max_fps": "60"})
    {'min_duration': 5.0, 'max_fps': 60.0}
    >>> parse_filters({"dataset": "pexels", "min_height": "1080"})
    {'min_height': 1080.0}
    >>> parse_filters({})
    {}
    """
    filters = {}
    for key, val in (args.items() if hasattr(args, 'items') else ((k, args[k]) for k in args)):
        if is_filter_key(key) and val is not None and val != "":
            filters[key] = float(val)
    return filters


def parse_pagination(args):
    """
    Extract pagination, sort, and ternary filter params from a dict-like object.
    Works with Flask request.args or plain dict. Pure function.

    Returns (page, page_size, sort_key, sort_dir, thumb_filter, fav_filter, random_seed).

    >>> parse_pagination({"page": 2, "page_size": 100, "sort": "duration", "sort_dir": "asc"})
    (2, 100, 'duration', 'asc', 'any', 'any', 0)
    >>> parse_pagination({})
    (1, 200, '', 'desc', 'any', 'any', 0)
    """
    g = args.get
    page = int(g("page", 1))
    page_size = int(g("page_size", 200))
    sort_key = g("sort", "")
    sort_dir = g("sort_dir", "desc")
    thumb_filter = g("thumb_filter", "any")
    fav_filter = g("fav_filter", "any")
    random_seed = int(g("random_seed", 0))
    return page, page_size, sort_key, sort_dir, thumb_filter, fav_filter, random_seed


def load_favorites(path):
    """
    Load favorites from a JSON file. Returns dict {dataset: [video_names]}.
    Pure function (reads filesystem).

    >>> load_favorites("/nonexistent_xyz_path")
    {}
    """
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def save_favorites(data, path):
    """Save favorites dict to a JSON file. Atomic write (temp+rename)."""
    save_json_atomic(data, path)


def resolve_sample_path(datasets_dir, dataset, video_name):
    """
    Compute the full filesystem path to a sample directory using shard routing.

    Pure function.

    >>> import os
    >>> p = resolve_sample_path("/data", "pexels", "19012581")
    >>> "samples" in p
    True
    """
    dataset_dir = os.path.join(datasets_dir, dataset)
    return sample_dir(dataset_dir, video_name)


def load_vector_indices(cache_dir):
    """
    Load all vector indices from cache/ directory. Generic: finds all
    {prefix}_index.faiss files and loads their corresponding data.

    Pure function (reads filesystem).

    Returns dict: {prefix: {video_names, embeddings, faiss_index}} or empty dict.

    >>> load_vector_indices("/nonexistent_xyz_dir")
    {}
    """
    import faiss

    indices = {}
    if not os.path.isdir(cache_dir):
        return indices

    # Find all FAISS index files
    for filename in os.listdir(cache_dir):
        if filename.endswith("_index.faiss"):
            prefix = filename.rsplit("_index.faiss", 1)[0]
            names_path = os.path.join(cache_dir, f"{prefix}_names.json")
            emb_path = os.path.join(cache_dir, f"{prefix}_embeddings.npz")
            index_path = os.path.join(cache_dir, filename)

            if os.path.exists(names_path) and os.path.exists(emb_path):
                with open(names_path) as f:
                    video_names = json.load(f)
                data = np.load(emb_path)
                embeddings = data["embeddings"]
                faiss_index = faiss.read_index(index_path)
                indices[prefix] = {
                    "video_names": video_names,
                    "embeddings": embeddings,
                    "faiss_index": faiss_index,
                }
                print(f"    Loaded {prefix} index: {len(video_names)} vectors")

    return indices


def load_json_dicts(cache_dir):
    """
    Load all JSON dict files from cache/ directory. Generic: reads
    cache_manifest.json to find which files are json_dict targets.

    Falls back to loading video_metadata.json and video_stats.json if no
    manifest exists (backward compat with first aggregation run).

    Returns dict: {target_name: data_dict}.

    >>> load_json_dicts("/nonexistent_xyz_dir")
    {}
    """
    result = {}
    if not os.path.isdir(cache_dir):
        return result

    manifest_path = os.path.join(cache_dir, "cache_manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)
        targets = list(manifest.get("json_dicts", {}).keys())
    else:
        # Fallback: known target names
        targets = ["video_metadata.json", "video_stats.json"]

    for target in targets:
        path = os.path.join(cache_dir, target)
        if os.path.exists(path):
            with open(path) as f:
                result[target] = json.load(f)

    return result


def load_dataset(name, datasets_dir):
    """
    Load a single dataset from its cache/ directory.

    Loads JSON dicts and vector indices generically based on what the
    aggregator produced (driven by processor plugin aggregation rules).
    """
    dataset_dir = os.path.join(datasets_dir, name)
    cache_dir = os.path.join(dataset_dir, "cache")
    manifest_path = os.path.join(dataset_dir, "manifest.json")

    if not os.path.exists(manifest_path):
        print(f"  Skipping dataset '{name}': no manifest at {manifest_path}")
        return None

    print(f"  Loading dataset '{name}'...")
    with open(manifest_path) as f:
        entries = json.load(f)

    # Build caption lookup
    caption_map = {e["video_name"]: e["caption"] for e in entries}

    result = {
        "entries": entries,
        "caption_map": caption_map,
        "video_metadata": None,
        "video_stats": None,
        "metadata_stats": {},
        "vector_indices": {},  # {prefix: {video_names, embeddings, faiss_index}}
    }

    # Load JSON dicts generically
    json_dicts = load_json_dicts(cache_dir)
    if "video_metadata.json" in json_dicts:
        result["video_metadata"] = json_dicts["video_metadata.json"]
        print(f"    Loaded metadata for {len(result['video_metadata'])} videos")
    if "video_stats.json" in json_dicts:
        result["video_stats"] = json_dicts["video_stats.json"]
        print(f"    Loaded stats for {len(result['video_stats'])} videos")

    # Load all vector indices generically
    result["vector_indices"] = load_vector_indices(cache_dir)
    if not result["vector_indices"]:
        print(f"    No vector indices found (fuzzy search only)")

    # Compute metadata stats for filter UI
    result["metadata_stats"] = compute_metadata_stats(result["video_metadata"], result["video_stats"])

    print(f"    {len(entries)} videos loaded")
    return result


def get_vector_index(ds, prefix="clip"):
    """
    Get a vector index from a dataset by prefix. Returns the index dict
    or None if not available. Pure function.

    >>> get_vector_index({"vector_indices": {}}, "clip") is None
    True
    >>> get_vector_index({"vector_indices": {"clip": {"video_names": ["a"]}}}, "clip")
    {'video_names': ['a']}
    """
    return ds.get("vector_indices", {}).get(prefix)


def create_app(port=8899):
    """Create and run the Flask app."""
    app = Flask(__name__, static_folder=os.path.join(REPO_ROOT, "static"))
    CORS(app)

    # Disable caching for static files during development
    @app.after_request
    def add_no_cache(response):
        if 'text/html' in response.content_type or 'javascript' in response.content_type or 'text/css' in response.content_type:
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    datasets_dir = os.path.join(REPO_ROOT, "datasets")

    print("Loading datasets...")
    if os.path.exists(datasets_dir):
        for name in sorted(os.listdir(datasets_dir)):
            ds_path = os.path.join(datasets_dir, name)
            if os.path.isdir(ds_path):
                ds = load_dataset(name, datasets_dir)
                if ds:
                    DATASETS[name] = ds

    if not DATASETS:
        print("WARNING: No datasets loaded! Run the preprocessing pipeline first.")
    else:
        print(f"Loaded {len(DATASETS)} dataset(s): {list(DATASETS.keys())}")

    # Load favorites
    global FAVORITES
    FAVORITES = load_favorites(FAVORITES_PATH)
    fav_total = sum(len(v) for v in FAVORITES.values())
    if fav_total:
        print(f"Loaded {fav_total} favorites across {len(FAVORITES)} dataset(s)")

    def enrich_results(results, ds, thumb_filter="any", fav_filter="any", fav_set=None):
        """
        Attach metadata and stats to each result item.
        Apply ternary filters: thumb_filter and fav_filter ('any'|'only'|'none').
        """
        meta = ds.get("video_metadata") or {}
        stats_data = ds.get("video_stats") or {}
        fav_set = fav_set or set()
        enriched = []
        for r in results:
            name = r["video_name"]
            has_thumb = name in meta
            is_fav = name in fav_set
            if thumb_filter == "only" and not has_thumb:
                continue
            if thumb_filter == "none" and has_thumb:
                continue
            if fav_filter == "only" and not is_fav:
                continue
            if fav_filter == "none" and is_fav:
                continue
            if name in meta:
                r["metadata"] = meta[name]
            if name in stats_data:
                r["stats"] = stats_data[name]
            enriched.append(r)
        return enriched

    def compute_result_histograms(results, metadata_stats, bins=60):
        """
        Compute histogram bin counts from enriched search results.
        Uses stable axis ranges (lo/hi) from full-dataset metadata_stats.
        Always returns an entry for every field in metadata_stats,
        even if no results have that field (zero counts).
        Returns {field: {lo, hi, counts, count}}.
        """
        # Collect values per field from results
        fields = {}
        for r in results:
            if "score" in r and isinstance(r["score"], (int, float)):
                fields.setdefault("score", []).append(r["score"])
            for source in [r.get("metadata") or {}, r.get("stats") or {}]:
                for k, v in source.items():
                    if isinstance(v, (int, float)):
                        fields.setdefault(k, []).append(v)

        # Build histograms for ALL metadata_stats fields (stable set)
        histograms = {}
        for field, stats in metadata_stats.items():
            lo = stats["min"]
            hi = stats["max"]
            values = fields.get(field, [])
            counts = bin_values(values, lo, hi, bins)
            histograms[field] = {"lo": lo, "hi": hi, "counts": counts, "count": len(values)}
        return histograms

    def post_process(results, ds, dataset, filters, thumb_filter, fav_filter, sort_key, sort_dir, page, page_size, random_seed=0):
        """
        Shared pipeline: filter → enrich → sort → histograms → paginate.
        Returns (page_results, total_count, result_histograms).
        """
        if filters:
            results = apply_filters(results, ds["video_metadata"], filters, ds["video_stats"])
        fav_set = set(FAVORITES.get(dataset, []))
        enriched = enrich_results(results, ds, thumb_filter=thumb_filter, fav_filter=fav_filter, fav_set=fav_set)
        sorted_results = sort_results(enriched, sort_key, sort_dir, random_seed)
        total = len(sorted_results)
        result_histograms = compute_result_histograms(sorted_results, ds["metadata_stats"])
        page_results = paginate(sorted_results, page, page_size)
        return page_results, total, result_histograms

    # --- Routes ---

    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/assets/<path:filepath>")
    def serve_assets(filepath):
        """Serve Vite build assets (JS, CSS with hashed filenames)."""
        return send_from_directory(os.path.join(app.static_folder, "assets"), filepath)

    @app.route("/thumbnails/<dataset>/<video_name>/<path:filename>")
    def serve_thumbnail(dataset, video_name, filename):
        """
        Serve a file from a sample directory with transparent shard routing.

        URL: /thumbnails/pexels/19012581/thumb_middle.jpg
        Resolves: datasets/pexels/samples/<shard>/<sample_id>/thumb_middle.jpg

        The frontend never sees the shard — this route handles the mapping.
        """
        sd = resolve_sample_path(datasets_dir, dataset, video_name)
        if not os.path.isdir(sd):
            return jsonify({"error": f"Sample directory not found for {video_name}"}), 404
        filepath = os.path.join(sd, filename)
        if not os.path.exists(filepath):
            return jsonify({"error": f"File not found: {filename}"}), 404
        return send_from_directory(sd, filename)

    @app.route("/api/video/<dataset>/<video_name>")
    def serve_video(dataset, video_name):
        """Stream video file for playback."""
        if dataset not in DATASETS:
            return jsonify({"error": f"Unknown dataset: {dataset}"}), 404

        ds = DATASETS[dataset]
        entry = next((e for e in ds["entries"] if e["video_name"] == video_name), None)
        if not entry:
            return jsonify({"error": "Video not found"}), 404

        source_path = entry["source_path"]
        if not os.path.exists(source_path):
            return jsonify({"error": f"Video file not found: {source_path}"}), 404

        directory = os.path.dirname(source_path)
        filename = os.path.basename(source_path)
        return send_from_directory(directory, filename, mimetype="video/mp4")

    @app.route("/api/datasets")
    def list_datasets():
        result = {}
        for name, ds in DATASETS.items():
            vi = ds.get("vector_indices", {})
            result[name] = {
                "count": len(ds["entries"]),
                "has_clip": "clip" in vi,
                "has_metadata": ds["video_metadata"] is not None,
                "vector_indices": list(vi.keys()),
            }
        return jsonify(result)

    @app.route("/api/config")
    def config():
        """Shared constants the frontend needs."""
        from preprocess.processors.ingest import SPRITE_COLS, SPRITE_ROWS
        return jsonify({
            "sprite_cols": SPRITE_COLS,
            "sprite_rows": SPRITE_ROWS,
            "sprite_frames": SPRITE_COLS * SPRITE_ROWS,
        })

    @app.route("/api/field_info")
    def field_info():
        """All field descriptions and artifact metadata from processor plugins."""
        from preprocess.processors import discover_processors, collect_field_info, collect_artifact_info

        all_procs = discover_processors()
        plugin_fields = collect_field_info(all_procs)
        image_artifacts, data_artifacts = collect_artifact_info(all_procs)

        # Server-only fields (not from any processor)
        all_fields = {
            "score": {"label": "Score (CLIP)", "description": "Cosine similarity (inner product of L2-normalized vectors) between the CLIP text embedding of the search query and the CLIP image embedding of the video's middle frame. Model: openai/clip-vit-base-patch32 (512-dim). Text encoded at query time, image embeddings pre-computed. Range: ~0 to ~0.4 in practice. Higher = more visually similar to query text.", "dtype": "float"},
        }
        all_fields.update(plugin_fields)

        return jsonify({
            "fields": all_fields,
            "image_artifacts": image_artifacts,
            "data_artifacts": data_artifacts,
        })

    @app.route("/api/status/<dataset>")
    def dataset_status(dataset):
        """
        Fresh-from-disk data counts for reload-available detection.

        Reads cache_manifest.json from disk each time (not in-memory data)
        so the frontend can detect when new samples have been processed
        since the server started.
        """
        if dataset not in DATASETS:
            return jsonify({"error": f"Unknown dataset: {dataset}"}), 404
        cache_manifest_path = os.path.join(datasets_dir, dataset, "cache", "cache_manifest.json")
        status = {}
        if os.path.exists(cache_manifest_path):
            with open(cache_manifest_path) as f:
                manifest = json.load(f)
            status["total_samples"] = manifest.get("total_samples", 0)
            for target, info in manifest.get("json_dicts", {}).items():
                key = target.replace(".json", "")
                status[key] = info.get("count", 0)
            for target, info in manifest.get("vector_indices", {}).items():
                status[target] = info.get("count", 0)
        return jsonify(status)

    @app.route("/api/metadata_stats/<dataset>")
    def metadata_stats(dataset):
        if dataset not in DATASETS:
            return jsonify({"error": f"Unknown dataset: {dataset}"}), 404
        return jsonify(DATASETS[dataset]["metadata_stats"])

    @app.route("/api/histograms/<dataset>")
    def histograms(dataset):
        """
        Return histogram bin counts for all numeric fields across the full dataset.
        Stable: does not depend on search query or filters.
        """
        if dataset not in DATASETS:
            return jsonify({"error": f"Unknown dataset: {dataset}"}), 404

        ds = DATASETS[dataset]
        bins = min(int(request.args.get("bins", 60)), 1000)
        result = compute_histograms(ds, bins)
        return jsonify(result)

    def compute_histograms(ds, bins=60):
        """
        Compute histogram bin counts for all numeric metadata/stats fields.
        Pure function (given dataset data).
        """
        histograms = {}
        fields = collect_numeric_fields(
            ds.get("video_metadata") or {},
            ds.get("video_stats") or {},
        )

        for field, values in fields.items():
            if not values:
                continue
            lo = min(values)
            hi = max(values)
            counts = bin_values(values, lo, hi, bins)
            histograms[field] = {"lo": lo, "hi": hi, "counts": counts, "count": len(values)}

        return histograms

    @app.route("/api/search/fuzzy")
    def search_fuzzy():
        dataset = request.args.get("dataset", "pexels")
        query = request.args.get("q", "")
        filters = parse_filters(request.args)
        page, page_size, sort_key, sort_dir, thumb_filter, fav_filter, random_seed = parse_pagination(request.args)

        if dataset not in DATASETS:
            return jsonify({"error": f"Unknown dataset: {dataset}"}), 404

        ds = DATASETS[dataset]
        # Fuzzy returns all matches (no limit) — pagination handles the windowing
        results = fuzzy_search(ds["entries"], query, limit=len(ds["entries"]))

        formatted = [
            {
                "video_name": r["video_name"],
                "caption": r["caption"],
                "thumb_url": f"/thumbnails/{dataset}/{r['video_name']}/thumb_middle.jpg",
            }
            for r in results
        ]

        # Compute CLIP similarity scores so sort-by-score works in fuzzy mode too
        clip_idx = get_vector_index(ds, "clip")
        if query.strip() and clip_idx is not None:
            query_emb = encode_text(query)
            query_emb = l2_normalize(np.array(query_emb, dtype=np.float32).reshape(1, -1))
            name_to_idx = {n: i for i, n in enumerate(clip_idx["video_names"])}
            for r in formatted:
                idx = name_to_idx.get(r["video_name"])
                if idx is not None:
                    emb = clip_idx["embeddings"][idx].astype(np.float32).reshape(1, -1)
                    r["score"] = float((query_emb @ emb.T).item())

        page_results, total, result_histograms = post_process(formatted, ds, dataset, filters, thumb_filter, fav_filter, sort_key, sort_dir, page, page_size, random_seed)
        return jsonify({
            "results": page_results,
            "total": total,
            "page": page,
            "page_size": page_size,
            "query": query,
            "histograms": result_histograms,
        })

    @app.route("/api/search/clip")
    def search_clip():
        dataset = request.args.get("dataset", "pexels")
        query = request.args.get("q", "")
        index_name = request.args.get("index", "clip")
        filters = parse_filters(request.args)
        page, page_size, sort_key, sort_dir, thumb_filter, fav_filter, random_seed = parse_pagination(request.args)

        if dataset not in DATASETS:
            return jsonify({"error": f"Unknown dataset: {dataset}"}), 404

        ds = DATASETS[dataset]
        vi = get_vector_index(ds, index_name)
        if vi is None:
            available = list(ds.get("vector_indices", {}).keys())
            return jsonify({"error": f"Vector index '{index_name}' not available. Available: {available}"}), 400

        query_emb = encode_text(query)
        # Return all indexed vectors — pagination handles the windowing
        results = clip_search(query_emb, vi["faiss_index"], vi["video_names"], k=len(vi["video_names"]))

        for r in results:
            r["caption"] = ds["caption_map"].get(r["video_name"], "")
            r["thumb_url"] = f"/thumbnails/{dataset}/{r['video_name']}/thumb_middle.jpg"

        page_results, total, result_histograms = post_process(results, ds, dataset, filters, thumb_filter, fav_filter, sort_key, sort_dir, page, page_size, random_seed)
        return jsonify({
            "results": page_results,
            "total": total,
            "page": page,
            "page_size": page_size,
            "query": query,
            "index": index_name,
            "histograms": result_histograms,
        })

    @app.route("/api/search/hull", methods=["POST"])
    def search_hull():
        data = request.get_json()
        dataset = data.get("dataset", "pexels")
        selected_names = data.get("selected", [])
        index_name = data.get("index", "clip")
        filters = parse_filters(data)
        page, page_size, sort_key, sort_dir, thumb_filter, fav_filter, random_seed = parse_pagination(data)

        if dataset not in DATASETS:
            return jsonify({"error": f"Unknown dataset: {dataset}"}), 404

        ds = DATASETS[dataset]
        vi = get_vector_index(ds, index_name)
        if vi is None:
            available = list(ds.get("vector_indices", {}).keys())
            return jsonify({"error": f"Vector index '{index_name}' not available. Available: {available}"}), 400

        name_to_idx = {n: i for i, n in enumerate(vi["video_names"])}
        selected_indices = [name_to_idx[n] for n in selected_names if n in name_to_idx]

        if not selected_indices:
            return jsonify({"error": "No valid selected videos found"}), 400

        selected_embs = vi["embeddings"][selected_indices]
        # Return all indexed vectors — pagination handles the windowing
        results = convex_hull_search(selected_embs, vi["embeddings"], vi["video_names"], k=len(vi["video_names"]))

        for r in results:
            r["caption"] = ds["caption_map"].get(r["video_name"], "")
            r["thumb_url"] = f"/thumbnails/{dataset}/{r['video_name']}/thumb_middle.jpg"

        page_results, total, result_histograms = post_process(results, ds, dataset, filters, thumb_filter, fav_filter, sort_key, sort_dir, page, page_size, random_seed)
        return jsonify({
            "results": page_results,
            "total": total,
            "page": page,
            "page_size": page_size,
            "selected_count": len(selected_indices),
            "index": index_name,
            "histograms": result_histograms,
        })

    @app.route("/api/video_info/<dataset>/<video_name>")
    def video_info(dataset, video_name):
        if dataset not in DATASETS:
            return jsonify({"error": f"Unknown dataset: {dataset}"}), 404

        ds = DATASETS[dataset]
        entry = next((e for e in ds["entries"] if e["video_name"] == video_name), None)
        if not entry:
            return jsonify({"error": "Video not found"}), 404

        # Thumbnails via shard routing (frontend URLs, server resolves shard)
        sd = resolve_sample_path(datasets_dir, dataset, video_name)
        thumbs = {}
        missing = []
        for frame in ("first", "middle", "last"):
            thumb_file = f"thumb_{frame}.jpg"
            if os.path.exists(os.path.join(sd, thumb_file)):
                thumbs[frame] = f"/thumbnails/{dataset}/{video_name}/{thumb_file}"
            else:
                missing.append(frame)

        response = {
            "video_name": entry["video_name"],
            "caption": entry.get("caption", ""),
            "source_path": entry["source_path"],
            "video_url": f"/api/video/{dataset}/{video_name}",
            "thumbnails": thumbs,
        }
        if missing:
            response["missing_thumbnails"] = missing

        # Include video metadata if available
        if ds["video_metadata"] and video_name in ds["video_metadata"]:
            response["metadata"] = ds["video_metadata"][video_name]

        # Include stats if available
        if ds["video_stats"] and video_name in ds["video_stats"]:
            response["stats"] = ds["video_stats"][video_name]

        # Flow sprite URL if it exists
        if os.path.exists(os.path.join(sd, "flow_sprite.jpg")):
            response["flow_sprite_url"] = f"/thumbnails/{dataset}/{video_name}/flow_sprite.jpg"

        return jsonify(response)

    @app.route("/api/favorites/<dataset>", methods=["GET"])
    def get_favorites(dataset):
        """Return the list of favorited video names for a dataset."""
        return jsonify({"favorites": FAVORITES.get(dataset, [])})

    @app.route("/api/favorites/<dataset>", methods=["POST"])
    def update_favorites(dataset):
        """Add or remove a video from favorites. Persists to disk."""
        data = request.get_json()
        video_name = data.get("video_name")
        action = data.get("action")  # "add" or "remove"
        if not video_name or action not in ("add", "remove"):
            return jsonify({"error": "Need video_name and action (add/remove)"}), 400

        if dataset not in FAVORITES:
            FAVORITES[dataset] = []
        fav_list = FAVORITES[dataset]

        if action == "add" and video_name not in fav_list:
            fav_list.append(video_name)
        elif action == "remove" and video_name in fav_list:
            fav_list.remove(video_name)

        save_favorites(FAVORITES, FAVORITES_PATH)
        return jsonify({"status": "ok", "count": len(fav_list)})

    @app.route("/api/reload/<dataset>")
    def reload_dataset(dataset):
        """
        Hot-reload a dataset's cache. Called when the frontend detects new data.
        Re-reads all cache/ files without restarting the server.
        """
        ds = load_dataset(dataset, datasets_dir)
        if ds:
            DATASETS[dataset] = ds
            return jsonify({"status": "ok", "entries": len(ds["entries"]),
                            "metadata": len(ds["video_metadata"]) if ds["video_metadata"] else 0,
                            "stats": len(ds["video_stats"]) if ds["video_stats"] else 0})
        return jsonify({"error": f"Failed to reload dataset '{dataset}'"}), 500

    print(f"\n{'='*60}")
    print(f"  Searchable Pexels v2 — http://0.0.0.0:{port}")
    print(f"{'='*60}\n")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    fire.Fire(create_app)
