"""
Perceptual hash processor. CPU-only, fast.

Usage:
    uv run python preprocess/processors/phash.py main --entries_json=... --dataset_dir=datasets/pexels
"""

import os
import json
import numpy as np
from PIL import Image

import fire

from preprocess.processors.base import Processor, run_pool_with_progress
from preprocess.video_utils import sample_dir, split_grid, summarize_sequence, sequence_variability, save_json_atomic
from preprocess.processors.ingest import SPRITE_COLS, SPRITE_ROWS


def _compute_phash(args):
    """Worker: compute phash stats for one sample."""
    video_name, dataset_dir = args
    sd = sample_dir(dataset_dir, video_name)
    sprite_path = os.path.join(sd, "sprite.jpg")
    out_path = os.path.join(sd, "phash_stats.json")

    if not os.path.exists(sprite_path):
        return (video_name, False, "No sprite.jpg")

    import imagehash
    sprite = np.array(Image.open(sprite_path).convert("RGB"))
    frames = split_grid(sprite, SPRITE_COLS, SPRITE_ROWS)

    hashes = [str(imagehash.phash(Image.fromarray(f))) for f in frames]
    distances = [
        imagehash.hex_to_hash(hashes[i]) - imagehash.hex_to_hash(hashes[i+1])
        for i in range(len(hashes) - 1)
    ]
    dists_float = [float(d) for d in distances]

    summary = summarize_sequence(dists_float)
    stats = {
        "phash_mean_change": summary["mean"],
        "phash_max_change": summary["max"],
        "phash_std_change": summary["std"],
        "phash_temporal_std": sequence_variability(dists_float),
    }

    save_json_atomic(stats, out_path)

    return (video_name, True, None)


class PhashProcessor(Processor):
    name = "phash"
    human_name = "Perceptual Hash"
    depends_on = ["ingest"]

    artifacts = [
        {"filename": "phash_stats.json", "label": "PHash Statistics", "description": "JSON: 4 fields from imagehash.phash (DCT-based 64-bit perceptual hash). 25 frames from sprite.jpg, 24 Hamming distances. phash_mean_change (0-64), phash_max_change, phash_std_change, phash_temporal_std.", "type": "data"},
    ]

    fields = {
        "phash_mean_change": {"label": "PHash Change", "description": "Mean Hamming distance between pHash of consecutive sprite frames. Range 0 (identical) to 64 (completely different).", "dtype": "float"},
        "phash_max_change": {"label": "PHash Max Change", "description": "Maximum Hamming distance between consecutive pHash frame pairs.", "dtype": "float"},
        "phash_std_change": {"label": "PHash Std", "description": "Std of 24 consecutive pHash Hamming distances.", "dtype": "float"},
        "phash_temporal_std": {"label": "PHash Variation", "description": "Std of first-differences of 24 pHash distances.", "dtype": "float"},
    }

    aggregation = [
        {"type": "json_dict", "source": "phash_stats.json", "target": "video_stats.json"},
    ]

    def process(self, entries, dataset_dir, workers=32):
        """Compute phash stats. CPU parallel via Pool."""
        args = [(e["video_name"], dataset_dir) for e in entries]
        run_pool_with_progress(_compute_phash, args, self.human_name, workers)


# ========================================================================
# Fire CLI
# ========================================================================

if __name__ == "__main__":
    fire.Fire({"main": PhashProcessor.cli_main})
