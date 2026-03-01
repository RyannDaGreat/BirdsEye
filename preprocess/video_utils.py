"""
Shared video utilities. Single source for sample paths and shared math.

Only functions used by 2+ processors live here. Processor-specific functions
live in their respective processor files.
"""

import hashlib
import os
import json
import tempfile

import numpy as np


# ========================================================================
# Sample path functions (used by all processors)
# ========================================================================

def sample_id(dataset, video_name):
    """
    Globally unique sample identifier. Prevents cross-dataset collisions.
    Pure function.

    >>> sample_id("pexels", "19012581")
    'pexels_19012581'
    """
    return f"{dataset}_{video_name}"


def sample_shard(sid):
    """
    Two-level shard from sha256 of sample_id. Returns 'ab/cd'.
    65,536 buckets. Pure function.

    >>> len(sample_shard("pexels_19012581").split(os.sep))
    2
    """
    h = hashlib.sha256(sid.encode()).hexdigest()
    return os.path.join(h[:2], h[2:4])


def sample_dir(dataset_dir, video_name):
    """Full path to a sample's artifact directory. Pure function."""
    dataset = os.path.basename(dataset_dir)
    sid = sample_id(dataset, video_name)
    return os.path.join(dataset_dir, "samples", sample_shard(sid), sid)


# ========================================================================
# Shared math (used by phash + raft_flow)
# ========================================================================

def split_grid(image_array, cols, rows):
    """
    Split grid image (numpy array) into cell images. Pure function.

    >>> split_grid(np.zeros((50, 100, 3), dtype=np.uint8), 5, 5)[0].shape
    (10, 20, 3)
    """
    h, w = image_array.shape[:2]
    cell_h, cell_w = h // rows, w // cols
    return [image_array[r*cell_h:(r+1)*cell_h, c*cell_w:(c+1)*cell_w]
            for r in range(rows) for c in range(cols)]


def summarize_sequence(values):
    """
    Summary stats: {mean, max, min, std}. Pure function.

    >>> summarize_sequence([1.0, 2.0, 3.0])['mean']
    2.0
    """
    if not values:
        return {"mean": 0.0, "max": 0.0, "min": 0.0, "std": 0.0}
    arr = np.array(values, dtype=float)
    return {
        "mean": round(float(arr.mean()), 4),
        "max": round(float(arr.max()), 4),
        "min": round(float(arr.min()), 4),
        "std": round(float(arr.std()), 4),
    }


def sequence_variability(values):
    """
    Std of first-differences. Pure function.

    >>> sequence_variability([1.0, 3.0, 2.0])
    0.5
    """
    if len(values) < 2:
        return 0.0
    return round(float(np.std(np.diff(values))), 4)


# ========================================================================
# I/O utilities
# ========================================================================

def atomic_write(path, writer_fn, suffix=".tmp"):
    """
    Atomic file write: create temp in same directory, write, rename.

    writer_fn(tmp_path) performs the actual write. os.rename is atomic on
    POSIX when source and dest are on the same filesystem — guaranteed here
    because mkstemp uses dir=target_dir.

    CRITICAL: Never use tempfile.mkstemp() without dir= for atomic writes.
    If the temp file lands on a different mount (e.g. /tmp vs NFS), rename
    becomes a copy+delete and is NOT atomic.
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


def save_json_atomic(data, path):
    """Atomic JSON save: temp file + rename. Safe for NFS."""
    def write(tmp):
        with open(tmp, "w") as f:
            json.dump(data, f)
    atomic_write(path, write)


def save_npy_atomic(array, path):
    """Atomic numpy .npy save: temp file + rename. Safe for NFS."""
    def write(tmp):
        np.save(tmp, array)
    atomic_write(path, write, suffix=".tmp.npy")


def save_npz_atomic(path, **arrays):
    """Atomic numpy .npz save: temp file + rename. Safe for NFS."""
    def write(tmp):
        np.savez_compressed(tmp, **arrays)
    atomic_write(path, write, suffix=".tmp.npz")


def save_faiss_atomic(index, path):
    """Atomic FAISS index save: temp file + rename. Safe for NFS."""
    import faiss
    def write(tmp):
        faiss.write_index(index, tmp)
    atomic_write(path, write, suffix=".tmp.faiss")


def load_json(path):
    """Load JSON, return empty dict if missing."""
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)
