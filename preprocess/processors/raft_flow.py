"""
RAFT optical flow processor. Uses all GPUs via self-calling subprocess.

Usage:
    uv run python preprocess/processors/raft_flow.py main --entries_json=... --dataset_dir=datasets/pexels
    uv run python preprocess/processors/raft_flow.py gpu_worker --list_path=/tmp/samples.json --gpu_id=0
"""

import os
import json
import sys

import numpy as np
import fire

from preprocess.processors.base import Processor, run_gpu_subprocess, distribute_across_gpus
from preprocess.video_utils import split_grid, summarize_sequence, sequence_variability
from preprocess.processors.ingest import SPRITE_COLS, SPRITE_ROWS


FLOW_MAX_DIM = 256


# ========================================================================
# Math — private to raft_flow
# ========================================================================

def vector_magnitude(dx, dy):
    """
    Per-element magnitude of 2D vector field. Pure function.

    (H, W) float, (H, W) float -> (H, W) float

    >>> vector_magnitude(np.array([3.0]), np.array([4.0]))
    array([5.])
    >>> vector_magnitude(np.array([[0.0, 3.0]]), np.array([[0.0, 4.0]]))[0, 1]
    5.0
    """
    return np.sqrt(dx ** 2 + dy ** 2)


# ========================================================================
# GPU worker helpers — run in subprocess
# ========================================================================

def _resize_for_flow(frame, max_dim):
    """Resize numpy frame for flow computation. Pure function."""
    from PIL import Image
    h, w = frame.shape[:2]
    if w >= h:
        new_w, new_h = max_dim, max(1, int(h * max_dim / w))
    else:
        new_h, new_w = max_dim, max(1, int(w * max_dim / h))
    return np.array(Image.fromarray(frame).resize((new_w, new_h), Image.LANCZOS))


def _load_sprite(sample):
    """Prefetch: load and split sprite. Returns (video_name, small_frames_or_None)."""
    from PIL import Image
    path = os.path.join(sample["sample_dir"], "sprite.jpg")
    if not os.path.exists(path):
        return sample["video_name"], None
    sprite = np.array(Image.open(path).convert("RGB"))
    frames = split_grid(sprite, SPRITE_COLS, SPRITE_ROWS)
    small = [_resize_for_flow(f, FLOW_MAX_DIM) for f in frames]
    return sample["video_name"], small


def _gpu_worker_fn(args):
    """Process a slice of samples on one GPU. Called via torch.multiprocessing.Pool."""
    gpu_id, samples = args
    device = f"cuda:{gpu_id}"
    from datetime import datetime

    def log(msg):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"  [{ts}] GPU {gpu_id}: {msg}", flush=True)

    from concurrent.futures import ThreadPoolExecutor

    # Load RAFT
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, os.path.join(repo_root, "libs", "CommonSource"))
    from raft import RaftOpticalFlow
    import rp

    log("Loading RAFT model...")
    raft = RaftOpticalFlow(device=device, version='small')
    log(f"Model loaded. Processing {len(samples)} samples...")

    prefetch = ThreadPoolExecutor(max_workers=4)
    done = 0
    skipped = 0
    failed = 0
    fail_names = []

    # Process in chunks for visible progress
    for chunk_start in range(0, len(samples), 16):
        chunk = samples[chunk_start:chunk_start + 16]

        # Prefetch sprites for this chunk
        futures = {prefetch.submit(_load_sprite, s): s for s in chunk}

        for future in futures:
            video_name, small_frames = future.result()
            sd = futures[future]["sample_dir"]

            if small_frames is None:
                log(f"  SKIP {video_name}: no sprite")
                skipped += 1
                done += 1
                continue

            try:
                # Compute 24 flow pairs
                magnitudes = []
                for i in range(len(small_frames) - 1):
                    flow = raft(small_frames[i], small_frames[i + 1])
                    flow_np = rp.as_numpy_array(flow)
                    mag = float(vector_magnitude(flow_np[0], flow_np[1]).mean())
                    magnitudes.append(mag)

                summary = summarize_sequence(magnitudes)
                stats = {
                    "flow_mean_magnitude": summary["mean"],
                    "flow_max_magnitude": summary["max"],
                    "flow_min_magnitude": summary["min"],
                    "flow_std_magnitude": summary["std"],
                    "flow_temporal_std": sequence_variability(magnitudes),
                }

                with open(os.path.join(sd, "flow_stats.json"), "w") as f:
                    json.dump(stats, f, indent=2)

            except Exception as e:
                log(f"  FAIL {video_name}: {e}")
                failed += 1
                fail_names.append(video_name)

            done += 1

        log(f"{done}/{len(samples)} samples ({done * 100 // len(samples)}%)")

    log(f"Summary: {done - skipped - failed} ok, {skipped} skipped, {failed} failed")
    if fail_names:
        log(f"Failed samples: {fail_names[:20]}{'...' if len(fail_names) > 20 else ''}")


def gpu_worker(list_path):
    """
    Subprocess entry point for CUDA-isolated GPU work.
    Distributes across all available GPUs via torch.multiprocessing.Pool.

    Args:
        list_path: JSON file with [{video_name, sample_dir}, ...]
    """
    with open(list_path) as f:
        samples = json.load(f)

    distribute_across_gpus(
        label="RAFT",
        samples=samples,
        worker_fn=_gpu_worker_fn,
    )


# ========================================================================
# Processor class
# ========================================================================

class RaftFlowProcessor(Processor):
    name = "raft_flow"
    human_name = "Optical Flow (RAFT)"
    depends_on = ["ingest"]

    artifacts = [
        {"filename": "flow_stats.json", "label": "Flow Statistics", "description": "JSON: 5 flow fields from RAFT (torchvision raft_small, C+T+V2). 25 sprite frames, 24 flow pairs at 256px.", "type": "data"},
    ]

    fields = {
        "flow_mean_magnitude": {"label": "Flow Magnitude", "description": "Mean flow magnitude across 24 frame pairs. RAFT raft_small at 256px.", "dtype": "float"},
        "flow_max_magnitude": {"label": "Flow Max", "description": "Max of 24 per-pair mean flow magnitudes.", "dtype": "float"},
        "flow_min_magnitude": {"label": "Flow Min", "description": "Min of 24 per-pair mean flow magnitudes.", "dtype": "float"},
        "flow_std_magnitude": {"label": "Flow Std", "description": "Std of 24 per-pair mean flow magnitudes.", "dtype": "float"},
        "flow_temporal_std": {"label": "Flow Variation", "description": "Std of first-differences of 24 flow magnitudes.", "dtype": "float"},
    }

    aggregation = [
        {"type": "json_dict", "source": "flow_stats.json", "target": "video_stats.json"},
    ]

    def process(self, entries, dataset_dir, workers=32):
        """Run RAFT as subprocess for CUDA isolation. Self-calls gpu_worker via Fire."""
        run_gpu_subprocess(entries, dataset_dir, __file__, self.human_name)


# ========================================================================
# Fire CLI
# ========================================================================

if __name__ == "__main__":
    fire.Fire({"main": RaftFlowProcessor.cli_main, "gpu_worker": gpu_worker})
