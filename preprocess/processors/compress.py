"""
Compression ladder processor: single-decode, multi-output ffmpeg cascade.

Decodes each source video ONCE and produces up to 6 resolution proxy files
(1080p, 720p, 480p, 360p, 240p, 144p) in a single ffmpeg invocation.
All downstream processors can read from these smaller proxies instead of
the original 1080-1440p source, yielding ~10x decode speedup.

Resolution refers to the SMALLER dimension (not always height):
    Landscape (w>h): height is smaller → height = target
    Portrait  (w≤h): width  is smaller → width  = target
    "480p" always means the smallest side is ≤480px.

Videos whose smaller dimension is already ≤ target are NOT upscaled.

Benchmark: single-decode 6-output cascade (11 videos, 1080-1440p H.264, 96 cores)
┌─────────────────────────────────┬──────────┬───────────┬──────────┐
│ Approach                        │ Time     │ Per-video │ Speedup  │
├─────────────────────────────────┼──────────┼───────────┼──────────┤
│ 6 separate ffmpeg calls         │ 13.67s   │ 1.24s     │ 1.0x     │
│ Single-decode 6-output cascade  │ 9.81s    │ 0.89s     │ 1.4x     │
└─────────────────────────────────┴──────────┴───────────┴──────────┘

Preset comparison (3 videos, CRF 28):
┌────────────┬──────────┬──────────┬──────────┬───────────────────────┐
│ Preset     │ PSNR(dB) │ Size(KB) │ Encode/s │ Decode vid/s          │
├────────────┼──────────┼──────────┼──────────┼───────────────────────┤
│ ultrafast  │ 30.44    │ 5656     │ 1.48     │ 12.5                  │
│ veryfast   │ 29.96    │ 1312     │ 1.50     │ 12.5 ← sweet spot    │
│ medium     │ 29.55    │ 1054     │ 2.29     │ 10.5                  │
│ veryslow   │ 29.44    │ 992      │ 16.62    │ 9.3                   │
└────────────┴──────────┴──────────┴──────────┴───────────────────────┘

veryfast: same encode/decode speed as ultrafast, -0.48 dB PSNR (imperceptible),
but 77% smaller files (4.3x compression ratio).

Full dataset estimate (81,766 videos at 2.5 vid/s): ~9 hours, ~240 GB output.

Usage:
    uv run python preprocess/processors/compress.py main --entries_json=... --dataset_dir=datasets/pexels
"""

import os
import json
import subprocess

import fire

from preprocess.processors.base import Processor, run_pool_with_progress


# ========================================================================
# Constants
# ========================================================================

LADDER_RESOLUTIONS = [1080, 720, 480, 360, 240, 144]
PRESET = "veryfast"
CRF = 28
DEFAULT_WORKERS = 48  # Optimal for CPU x264 on 96-core (benchmarked)


# ========================================================================
# Pure functions
# ========================================================================

def min_dim_scale_filter(target_res):
    """
    Build ffmpeg scale filter that targets the SMALLER dimension.
    Pure function.

    For landscape (w>h): scales height to min(h, target), width auto (-2).
    For portrait  (w≤h): scales width  to min(w, target), height auto (-2).
    min() prevents upscaling. -2 ensures even dimensions (required by x264).
    flags=fast_bilinear is 2x faster than default lanczos scale.

    Examples:
        1920x1080 landscape @ 480p → -2:480 → 854x480
        1080x1920 portrait  @ 480p → 480:-2 → 480x854
        640x480   landscape @ 720p → -2:480 → 640x480 (no upscale)
        320x240   landscape @ 480p → -2:240 → 320x240 (no upscale)

    >>> min_dim_scale_filter(480)
    "scale='if(lte(iw,ih),min(iw,480),-2)':'if(gt(iw,ih),min(ih,480),-2)':flags=fast_bilinear"
    >>> min_dim_scale_filter(144)
    "scale='if(lte(iw,ih),min(iw,144),-2)':'if(gt(iw,ih),min(ih,144),-2)':flags=fast_bilinear"
    """
    return (
        f"scale="
        f"'if(lte(iw,ih),min(iw,{target_res}),-2)'"
        f":"
        f"'if(gt(iw,ih),min(ih,{target_res}),-2)'"
        f":flags=fast_bilinear"
    )


def artifact_filename(res):
    """
    Artifact filename for a given resolution. Pure function.

    >>> artifact_filename(480)
    'compress_480p.mp4'
    >>> artifact_filename(1080)
    'compress_1080p.mp4'
    """
    return f"compress_{res}p.mp4"


# ========================================================================
# Worker function for multiprocessing.Pool
# ========================================================================

_compress_processor = None  # Module-level ref for Pool workers


def _compress_one(args):
    """
    Worker: compress one video to all resolutions. Called via multiprocessing.Pool.

    Returns (video_name, success, error_msg_or_None).
    """
    entry, dataset_dir, resolutions, preset, crf = args
    video_name = entry["video_name"]

    sd = _compress_processor.ensure_sample_dir(entry, dataset_dir)
    video_path = os.path.join(sd, "video.mp4")

    if not os.path.exists(video_path):
        return (video_name, False, f"No video.mp4 at {sd}")

    # Check which resolutions still need to be produced
    needed = []
    for res in resolutions:
        out_path = os.path.join(sd, artifact_filename(res))
        if not os.path.exists(out_path):
            needed.append(res)

    if not needed:
        return (video_name, True, None)

    # Build ffmpeg command for only the needed resolutions
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", video_path]
    for res in sorted(needed, reverse=True):
        output_path = os.path.join(sd, artifact_filename(res))
        cmd.extend([
            "-vf", min_dim_scale_filter(res),
            "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-an", output_path,
        ])

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=600)
        if result.returncode != 0:
            stderr = result.stderr.decode(errors='replace')[:200]
            return (video_name, False, f"ffmpeg exit {result.returncode}: {stderr}")
    except subprocess.TimeoutExpired:
        return (video_name, False, "ffmpeg timeout (600s)")

    # Verify all outputs exist and are non-empty
    for res in needed:
        out_path = os.path.join(sd, artifact_filename(res))
        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            return (video_name, False, f"Missing or empty output: {artifact_filename(res)}")

    return (video_name, True, None)


# ========================================================================
# Processor class
# ========================================================================

class CompressProcessor(Processor):
    name = "compress"
    human_name = "Compression Ladder"
    depends_on = []

    artifacts = [
        {"filename": "compress_1080p.mp4", "label": "1080p Proxy", "description": "H.264 veryfast CRF 28 proxy, smaller dimension ≤ 1080px. Skipped if source is smaller. Single-decode multi-output ffmpeg cascade.", "type": "data"},
        {"filename": "compress_720p.mp4", "label": "720p Proxy", "description": "H.264 veryfast CRF 28 proxy, smaller dimension ≤ 720px. Skipped if source is smaller.", "type": "data"},
        {"filename": "compress_480p.mp4", "label": "480p Proxy", "description": "H.264 veryfast CRF 28 proxy, smaller dimension ≤ 480px. Primary proxy for downstream processors (10x faster decode than 1080p source).", "type": "data"},
        {"filename": "compress_360p.mp4", "label": "360p Proxy", "description": "H.264 veryfast CRF 28 proxy, smaller dimension ≤ 360px.", "type": "data"},
        {"filename": "compress_240p.mp4", "label": "240p Proxy", "description": "H.264 veryfast CRF 28 proxy, smaller dimension ≤ 240px.", "type": "data"},
        {"filename": "compress_144p.mp4", "label": "144p Proxy", "description": "H.264 veryfast CRF 28 proxy, smaller dimension ≤ 144px. Miniature thumbnail video.", "type": "data"},
    ]

    fields = {}

    preview_sections = [
        {"type": "side_by_side_videos", "label": "Compression Ladder", "priority": 50,
         "args": {"files": ["compress_1080p.mp4", "compress_720p.mp4", "compress_480p.mp4"],
                  "labels": ["1080p", "720p", "480p"]}},
    ]

    def process(self, entries, dataset_dir, workers=DEFAULT_WORKERS):
        """Compress videos to all ladder resolutions. CPU parallel via Pool."""
        global _compress_processor
        _compress_processor = self

        args = [
            (entry, dataset_dir, LADDER_RESOLUTIONS, PRESET, CRF)
            for entry in entries
        ]
        run_pool_with_progress(_compress_one, args, self.human_name, workers)


# ========================================================================
# Fire CLI
# ========================================================================

if __name__ == "__main__":
    fire.Fire({"main": CompressProcessor.cli_main})
