"""
Plugin-driven aggregator: build cache/ from per-sample artifacts in samples/.

Reads aggregation rules from processor plugins — no hardcoded file paths.
Two aggregation types:
  - json_dict:    merge per-sample JSON files into {video_name: data} dicts
  - vector_index: read per-sample .npy files, build FAISS IndexFlatIP

Incremental: reads existing cache_manifest.json and only processes new samples.
Use --clear_cache to force full rebuild.

Usage:
    uv run python preprocess/aggregator.py --dataset_dir datasets/pexels
    uv run python preprocess/aggregator.py --dataset_dir datasets/pexels --clear_cache
"""

import json
import os
import sys
import time

import numpy as np
import fire
from tqdm import tqdm

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from preprocess.video_utils import load_json, save_json_atomic


# ========================================================================
# Pure functions
# ========================================================================

def list_shard_pairs(samples_dir):
    """
    List all (shard1, shard2, path) tuples under samples/.
    Two-level hex sharding: samples/<xx>/<yy>/<sample_id>/.
    Pure function (reads filesystem).

    >>> list_shard_pairs("/nonexistent_dir_xyz")
    []
    """
    if not os.path.isdir(samples_dir):
        return []
    pairs = []
    for s1 in sorted(os.listdir(samples_dir)):
        s1_path = os.path.join(samples_dir, s1)
        if not os.path.isdir(s1_path):
            continue
        for s2 in sorted(os.listdir(s1_path)):
            s2_path = os.path.join(s1_path, s2)
            if os.path.isdir(s2_path):
                pairs.append((s1, s2, s2_path))
    return pairs


def discover_sample_dirs(samples_dir):
    """
    Walk samples/<shard1>/<shard2>/<sample_id>/ and return list of
    (sample_id, sample_dir_path) for each directory containing origins.json.

    Shows progress per shard pair (up to 256×256 = 65,536 buckets).
    Pure function (reads filesystem).

    >>> discover_sample_dirs("/nonexistent_dir_xyz")
    []
    """
    pairs = list_shard_pairs(samples_dir)
    results = []
    for s1, s2, s2_path in tqdm(pairs, desc="Scanning samples", unit="bucket"):
        for entry in os.listdir(s2_path):
            sample_path = os.path.join(s2_path, entry)
            if os.path.isdir(sample_path) and os.path.exists(os.path.join(sample_path, "origins.json")):
                results.append((entry, sample_path))
    return sorted(results)


def video_name_from_sample_id(sid):
    """
    Extract video_name from sample_id by stripping the dataset prefix.
    Pure function.

    >>> video_name_from_sample_id("pexels_19012581")
    '19012581'
    >>> video_name_from_sample_id("envato_12345")
    '12345'
    >>> video_name_from_sample_id("no_underscore")
    'underscore'
    """
    parts = sid.split("_", 1)
    return parts[1] if len(parts) > 1 else sid


def read_sample_json(sample_path, filename):
    """
    Read a JSON file from a sample directory. Returns dict or None.
    Pure function (reads filesystem).

    >>> read_sample_json("/nonexistent_xyz", "metadata.json") is None
    True
    """
    path = os.path.join(sample_path, filename)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def read_sample_numpy(sample_path, filename):
    """
    Read a .npy file from a sample directory. Returns ndarray or None.
    Pure function (reads filesystem).

    >>> read_sample_numpy("/nonexistent_xyz", "embedding.npy") is None
    True
    """
    path = os.path.join(sample_path, filename)
    if not os.path.exists(path):
        return None
    return np.load(path)


# ========================================================================
# Aggregation operations
# ========================================================================

def aggregate_json_dict(target_name, source_files, new_samples, cache_dir, clear_cache):
    """
    Aggregate per-sample JSON files into a single {video_name: merged_data} dict.

    Multiple source files per sample get merged into one dict per video.
    Writes to cache_dir/target_name. Incremental unless clear_cache=True.

    Args:
        target_name: output filename in cache/ (e.g., "video_metadata.json")
        source_files: list of (source_filename, proc_name) tuples
        new_samples: list of (sample_id, sample_path) for new samples only
        cache_dir: path to cache directory
        clear_cache: if True, ignore existing cache file

    Returns:
        int — total entries in the output dict
    """
    target_path = os.path.join(cache_dir, target_name)

    if clear_cache:
        merged = {}
    else:
        merged = load_json(target_path)

    source_names = [s for s, _ in source_files]
    proc_names = [p for _, p in source_files]
    desc = f"{target_name} ({', '.join(proc_names)})"

    for sid, path in tqdm(new_samples, desc=desc):
        vname = video_name_from_sample_id(sid)
        sample_data = {}
        for source_filename in source_names:
            data = read_sample_json(path, source_filename)
            if data:
                sample_data.update(data)
        if sample_data:
            if vname in merged:
                merged[vname].update(sample_data)
            else:
                merged[vname] = sample_data

    save_json_atomic(merged, target_path)
    print(f"  Saved {target_name}: {len(merged)} entries")
    return len(merged)


def aggregate_vector_index(rule, new_samples, cache_dir, clear_cache):
    """
    Aggregate per-sample numpy vectors into an npz + FAISS index.

    Reads per-sample .npy files, concatenates, builds FAISS IndexFlatIP.
    Writes: {prefix}_embeddings.npz, {prefix}_index.faiss, {prefix}_names.json.
    Incremental unless clear_cache=True.

    Args:
        rule: dict with keys: prefix, source, dim, proc_name
        new_samples: list of (sample_id, sample_path) for new samples only
        cache_dir: path to cache directory
        clear_cache: if True, ignore existing cache files

    Returns:
        int — total vectors in the index
    """
    import faiss

    prefix = rule["prefix"]
    source = rule["source"]
    dim = rule["dim"]

    names_path = os.path.join(cache_dir, f"{prefix}_names.json")
    emb_path = os.path.join(cache_dir, f"{prefix}_embeddings.npz")
    index_path = os.path.join(cache_dir, f"{prefix}_index.faiss")

    # Load existing
    if clear_cache:
        existing_names = []
        existing_embs = None
    else:
        if os.path.exists(names_path) and os.path.exists(emb_path):
            existing_names = load_json(names_path)
            if not isinstance(existing_names, list):
                existing_names = []
            existing_embs = np.load(emb_path)["embeddings"]
        else:
            existing_names = []
            existing_embs = None

    # Build name→embedding map from existing (preserves order, allows overwrite)
    name_to_emb = {}
    if existing_names and existing_embs is not None:
        for i, name in enumerate(existing_names):
            name_to_emb[name] = existing_embs[i].reshape(1, -1).astype(np.float16)

    # Read new vectors — overwrites existing (dedup) or adds new
    added = 0
    updated = 0
    for sid, path in tqdm(new_samples, desc=f"{prefix} vectors"):
        vname = video_name_from_sample_id(sid)
        vec = read_sample_numpy(path, source)
        if vec is not None:
            if vname in name_to_emb:
                updated += 1
            else:
                added += 1
            name_to_emb[vname] = vec.reshape(1, -1).astype(np.float16)

    if updated:
        print(f"  {prefix}: {added} new, {updated} updated (dedup)")

    # Convert back to parallel arrays
    if name_to_emb:
        all_names = sorted(name_to_emb.keys())
        all_embs = np.concatenate([name_to_emb[n] for n in all_names], axis=0)
        print(f"  Total {prefix} vectors: {len(all_names)} ({all_embs.shape})")

        # Save embeddings + names
        np.savez_compressed(emb_path, embeddings=all_embs)
        save_json_atomic(all_names, names_path)

        # Build FAISS index
        embs_f32 = all_embs.astype(np.float32)
        index = faiss.IndexFlatIP(embs_f32.shape[1])
        index.add(embs_f32)
        faiss.write_index(index, index_path)
        print(f"  Built {prefix} FAISS index: {index.ntotal} vectors")
        return len(all_names)
    else:
        print(f"  No {prefix} vectors found")
        return 0


# ========================================================================
# Main aggregation logic
# ========================================================================

def aggregate(dataset_dir="datasets/pexels", clear_cache=False, sample_list=None,
              only_processors=None):
    """
    Build cache/ from samples/. Plugin-driven, incremental by default.

    Reads aggregation rules from all discovered processors. No hardcoded paths.

    Args:
        dataset_dir: Path to dataset directory containing samples/
        clear_cache: If True, rebuild everything from scratch
        sample_list: Optional list of (sample_id, sample_path) to aggregate.
                     If provided, skips the expensive filesystem scan of all
                     sample dirs — much faster for batch-mode auto-aggregation.
        only_processors: Optional list of processor names to aggregate.
                         If provided, only runs aggregation rules from these
                         processors (e.g., ["clip"] skips phash/raft_flow rules).
    """
    from preprocess.processors import discover_processors, collect_aggregation_rules

    samples_dir = os.path.join(dataset_dir, "samples")
    cache_dir = os.path.join(dataset_dir, "cache")
    os.makedirs(cache_dir, exist_ok=True)

    manifest_path = os.path.join(cache_dir, "cache_manifest.json")

    # 1. Load previous cache manifest
    prev = {} if clear_cache else load_json(manifest_path)
    prev_names = set(prev.get("samples_included", []))
    if clear_cache:
        print("Clear cache requested — rebuilding everything from scratch")

    # 2. Discover samples to aggregate
    if sample_list is not None:
        # Batch mode: caller provides exactly which samples to aggregate (skip scan)
        new_samples = sample_list
        all_sids = sorted(prev_names | {sid for sid, _ in sample_list})
        print(f"  Batch aggregate: {len(new_samples)} samples (skip scan)")
    else:
        # Full scan mode: walk entire samples/ directory tree
        print(f"Scanning {samples_dir}...")
        all_samples = discover_sample_dirs(samples_dir)
        all_sids = [sid for sid, _ in all_samples]
        print(f"  Total samples: {len(all_samples)}")
        new_samples = [(sid, path) for sid, path in all_samples if sid not in prev_names]
        print(f"  New samples:   {len(new_samples)}")

    if not new_samples and not clear_cache:
        print("Nothing new to aggregate.")
        return

    # 3. Discover processors and collect aggregation rules
    all_processors = discover_processors()
    if only_processors is not None:
        active = {name: proc for name, proc in all_processors.items()
                  if name in only_processors}
        print(f"  Scoped to processors: {sorted(active.keys())}")
    else:
        active = all_processors
    json_dict_rules, vector_index_rules = collect_aggregation_rules(active)

    # 4. Run json_dict aggregations
    json_counts = {}
    for target_name, source_files in sorted(json_dict_rules.items()):
        print(f"\nAggregating {target_name}...")
        count = aggregate_json_dict(target_name, source_files, new_samples, cache_dir, clear_cache)
        json_counts[target_name] = count

    # 5. Run vector_index aggregations
    vector_counts = {}
    for rule in vector_index_rules:
        prefix = rule["prefix"]
        print(f"\nAggregating {prefix} vectors...")
        count = aggregate_vector_index(rule, new_samples, cache_dir, clear_cache)
        vector_counts[prefix] = count

    # 6. Save cache manifest
    manifest = {
        "samples_included": all_sids,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_samples": len(all_sids),
        "json_dicts": {name: {"count": count} for name, count in json_counts.items()},
        "vector_indices": {
            prefix: {"count": count, "dim": rule["dim"]}
            for rule in vector_index_rules
            for prefix in [rule["prefix"]]
            if (count := vector_counts.get(prefix, 0)) or True
        },
    }
    save_json_atomic(manifest, manifest_path)
    print(f"\nCache manifest saved: {len(all_sids)} samples included")
    print(f"  JSON dicts: {json_counts}")
    print(f"  Vector indices: {vector_counts}")
    print("Aggregation complete.")


if __name__ == "__main__":
    fire.Fire(aggregate)
