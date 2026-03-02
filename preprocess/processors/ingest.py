"""
Ingest processor: opens each video ONCE, extracts thumbnails + sprite + metadata.

This is the root processor. All downstream processors depend on its outputs.

Decode: PyAV with thread_type='AUTO' (benchmarked fastest at 3.3 vid/s, 16 workers, 96 cores).
Image ops: cv2 with INTER_AREA (faster than PIL/LANCZOS for downscaling).

Usage:
    uv run python preprocess/processors/ingest.py main --entries_json=... --dataset_dir=datasets/pexels
"""

import os
import json

import cv2
import numpy as np
import fire

from preprocess.processors.base import Processor, run_pool_with_progress
from preprocess.video_utils import save_json_atomic


# ========================================================================
# Constants
# ========================================================================

THUMB_HEIGHT = 512
THUMB_QUALITY = 30
SPRITE_COLS = 5
SPRITE_ROWS = 5
SPRITE_CELL_W = 192
SPRITE_CELL_H = 108
SPRITE_QUALITY = 80
DEFAULT_WORKERS = 16  # Optimal for PyAV AUTO threading on 96-core (benchmarked)


# ========================================================================
# Frame extraction (PyAV) — private to ingest
# ========================================================================

def extract_key_and_sprite_frames(video_path, num_sprite_frames=25):
    """
    Open video ONCE via PyAV, sequential scan collecting needed frames.

    Returns (key_frames, sprite_frames, metadata) where:
    - key_frames: {"first": ndarray(H,W,3 BGR), "middle": ..., "last": ...}
    - sprite_frames: list of num_sprite_frames ndarray(H,W,3 BGR)
    - metadata: {frame_count, fps, width, height}

    Uses PyAV with thread_type='AUTO' for optimal multi-threaded H.264 decode.
    Returns BGR numpy arrays (cv2 convention). Pure function.
    """
    import av

    container = av.open(video_path)
    stream = container.streams.video[0]
    stream.thread_type = 'AUTO'

    total = stream.frames
    if total == 0:
        duration = container.duration
        if duration:
            fps = float(stream.average_rate) if stream.average_rate else 30.0
            total = int(duration / 1_000_000 * fps)
    if total == 0:
        container.close()
        return {}, [], {}

    fps = float(stream.average_rate) if stream.average_rate else 30.0
    w = stream.codec_context.width
    h = stream.codec_context.height

    key_indices = [0, total // 2, max(0, total - 1)]
    sprite_indices = np.linspace(0, total - 1, num_sprite_frames, dtype=int).tolist()

    all_needed = set(key_indices + sprite_indices)
    max_needed = max(all_needed)

    collected = {}
    n = 0
    for frame in container.decode(video=0):
        if n in all_needed:
            collected[n] = frame.to_ndarray(format='bgr24')
        n += 1
        if n > max_needed:
            break
    container.close()

    if not collected:
        return {}, [], {}

    key_frames = {}
    for label, idx in zip(("first", "middle", "last"), key_indices):
        if idx in collected:
            key_frames[label] = collected[idx]

    sprite_frames = [collected.get(idx) for idx in sprite_indices]

    metadata = {
        "frame_count": total,
        "fps": round(fps, 3),
        "width": int(w),
        "height": int(h),
    }

    return key_frames, sprite_frames, metadata


# ========================================================================
# Image manipulation (cv2) — private to ingest
# ========================================================================

def resize_by_height_cv2(img, target_height):
    """
    Resize BGR ndarray to target height, preserving aspect ratio.
    Uses INTER_AREA for downscaling (anti-aliased, fast). Pure function.

    (H, W, C) uint8 BGR -> (target_height, W', C) uint8 BGR

    >>> resize_by_height_cv2(np.zeros((100, 200, 3), dtype=np.uint8), 50).shape
    (50, 100, 3)
    >>> resize_by_height_cv2(np.zeros((480, 640, 3), dtype=np.uint8), 512).shape
    (512, 683, 3)
    """
    h, w = img.shape[:2]
    ratio = target_height / h
    target_w = round(w * ratio)
    return cv2.resize(img, (target_w, target_height), interpolation=cv2.INTER_AREA)


def resize_contain_cv2(img, width, height):
    """
    Resize BGR ndarray to fit within (width, height), center on black canvas.
    Uses INTER_AREA for downscaling. Pure function.

    (H, W, C) uint8 BGR -> (height, width, C) uint8 BGR

    >>> resize_contain_cv2(np.zeros((200, 400, 3), dtype=np.uint8), 192, 108).shape
    (108, 192, 3)
    >>> resize_contain_cv2(np.zeros((100, 100, 3), dtype=np.uint8), 192, 108).shape
    (108, 192, 3)
    """
    h, w = img.shape[:2]
    scale = min(width / w, height / h)
    nw, nh = round(w * scale), round(h * scale)
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    y_off = (height - nh) // 2
    x_off = (width - nw) // 2
    canvas[y_off:y_off + nh, x_off:x_off + nw] = resized
    return canvas


def compose_sprite_cv2(frames, cols, rows, cell_w, cell_h):
    """
    Compose BGR ndarrays into a grid sprite sheet. Pure function.

    List of N x (H, W, C) uint8 BGR -> (rows*cell_h, cols*cell_w, C) uint8 BGR

    >>> compose_sprite_cv2([np.zeros((10,20,3), dtype=np.uint8)]*4, 2, 2, 20, 10).shape
    (20, 40, 3)
    >>> compose_sprite_cv2([np.zeros((480,640,3), dtype=np.uint8)]*25, 5, 5, 192, 108).shape
    (540, 960, 3)
    """
    sprite = np.zeros((rows * cell_h, cols * cell_w, 3), dtype=np.uint8)
    for i, frame in enumerate(frames):
        if frame is None or i >= cols * rows:
            continue
        cell = resize_contain_cv2(frame, cell_w, cell_h)
        row, col = divmod(i, cols)
        y = row * cell_h
        x = col * cell_w
        sprite[y:y + cell_h, x:x + cell_w] = cell
    return sprite


def encode_jpeg(img, quality=30):
    """
    Encode BGR ndarray to JPEG bytes. Pure function.

    >>> len(encode_jpeg(np.zeros((10, 10, 3), dtype=np.uint8))) > 0
    True
    """
    ok, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return buf.tobytes()


# ========================================================================
# Fast metadata probe (no frame decode)
# ========================================================================

def _probe_metadata(video_path):
    """
    Extract stream metadata without decoding any frames.

    Returns {frame_count, fps, width, height} or None on failure.
    """
    import av
    try:
        container = av.open(video_path)
        stream = container.streams.video[0]
        total = stream.frames
        if total == 0:
            duration = container.duration
            fps = float(stream.average_rate) if stream.average_rate else 30.0
            if duration:
                total = int(duration / 1_000_000 * fps)
        meta = {
            "frame_count": total,
            "fps": round(float(stream.average_rate) if stream.average_rate else 30.0, 3),
            "width": stream.codec_context.width,
            "height": stream.codec_context.height,
        }
        container.close()
        return meta
    except Exception as e:
        print(f"    WARN: Failed to probe metadata for {video_path}: {e}", flush=True)
        return None


# ========================================================================
# Proxy resolution selection
# ========================================================================

# Preferred proxy resolution for ingest (480p is 10x faster to decode than 1080p).
# Falls back to highest available proxy, then to original video.mp4.
PREFERRED_PROXY_RES = 480
PROXY_FALLBACK_ORDER = [480, 720, 360, 1080, 240, 144]


def select_video_source(sample_directory):
    """
    Select the best video source for frame extraction. Pure function.

    Preference: compress_480p.mp4 > compress_720p.mp4 > compress_360p.mp4 >
    compress_1080p.mp4 > compress_240p.mp4 > compress_144p.mp4 > video.mp4

    Returns (path, source_label) or (None, None) if nothing exists.

    >>> select_video_source("/nonexistent") == (None, None)
    True
    """
    for res in PROXY_FALLBACK_ORDER:
        path = os.path.join(sample_directory, f"compress_{res}p.mp4")
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path, f"compress_{res}p"

    # Fall back to original
    orig = os.path.join(sample_directory, "video.mp4")
    if os.path.exists(orig):
        return orig, "original"

    return None, None


# ========================================================================
# Worker function for multiprocessing.Pool
# ========================================================================

# Module-level ref to processor instance for Pool workers (set in process())
_processor_instance = None


def _process_one(args):
    """Worker: process one video. Called via multiprocessing.Pool."""
    entry, dataset_dir = args

    video_name = entry["video_name"]
    sd = _processor_instance.ensure_sample_dir(entry, dataset_dir)
    video_path, source_label = select_video_source(sd)

    if video_path is None:
        return (video_name, False, f"No video source at {sd}")

    # ONE video open, ONE sequential scan (from proxy for speed)
    try:
        key_frames, sprite_frames, proxy_meta = extract_key_and_sprite_frames(
            video_path, num_sprite_frames=SPRITE_COLS * SPRITE_ROWS
        )
    except Exception as e:
        # Proxy might be corrupt — try falling back to original
        if source_label != "original":
            original = os.path.join(sd, "video.mp4")
            if os.path.exists(original):
                try:
                    key_frames, sprite_frames, proxy_meta = extract_key_and_sprite_frames(
                        original, num_sprite_frames=SPRITE_COLS * SPRITE_ROWS
                    )
                    source_label = "original (fallback)"
                except Exception as e2:
                    return (video_name, False, f"Decode failed on proxy and original: {e2}")
            else:
                return (video_name, False, f"Corrupt proxy, no original: {e}")
        else:
            return (video_name, False, f"Decode failed: {e}")

    if not key_frames:
        return (video_name, False, "No frames extracted (0-length video?)")

    # Save thumbnails (512px height, aspect-preserved, JPEG)
    for name, frame in key_frames.items():
        out = os.path.join(sd, f"thumb_{name}.jpg")
        if not os.path.exists(out):
            resized = resize_by_height_cv2(frame, THUMB_HEIGHT)
            with open(out, "wb") as f:
                f.write(encode_jpeg(resized, THUMB_QUALITY))

    # Save sprite sheet (5x5 grid, 192x108 contain-padded)
    sprite_path = os.path.join(sd, "sprite.jpg")
    if not os.path.exists(sprite_path):
        sprite = compose_sprite_cv2(sprite_frames, SPRITE_COLS, SPRITE_ROWS, SPRITE_CELL_W, SPRITE_CELL_H)
        with open(sprite_path, "wb") as f:
            f.write(encode_jpeg(sprite, SPRITE_QUALITY))

    # Save metadata — always from ORIGINAL video (not proxy)
    meta_path = os.path.join(sd, "metadata.json")
    if not os.path.exists(meta_path):
        # Get real dimensions from original source
        original_path = os.path.join(sd, "video.mp4")
        if os.path.exists(original_path) and source_label != "original":
            # Quick probe: just open and read stream info, don't decode frames
            orig_meta = _probe_metadata(original_path)
            if orig_meta:
                proxy_meta.update({"width": orig_meta["width"], "height": orig_meta["height"],
                                   "frame_count": orig_meta.get("frame_count", proxy_meta["frame_count"]),
                                   "fps": orig_meta.get("fps", proxy_meta["fps"])})

        proxy_meta["duration"] = round(proxy_meta["frame_count"] / max(proxy_meta["fps"], 1e-6), 3)
        proxy_meta["file_size_mb"] = round(os.path.getsize(entry["source_path"]) / (1024 * 1024), 2)
        proxy_meta["num_frames"] = proxy_meta.pop("frame_count")
        save_json_atomic(proxy_meta, meta_path)

    return (video_name, True, None)


# ========================================================================
# Processor class
# ========================================================================

class IngestProcessor(Processor):
    name = "ingest"
    human_name = "Ingest"
    depends_on = ["compress"]

    artifacts = [
        {"filename": "thumb_first.jpg", "label": "First Frame", "description": "First video frame at 512px height, aspect-preserved, JPEG q=30. Extracted via PyAV sequential decode at frame 0.", "type": "image"},
        {"filename": "thumb_middle.jpg", "label": "Middle Frame", "description": "Middle video frame at 512px height. Frame index = total_frames // 2. Primary display image.", "type": "image"},
        {"filename": "thumb_last.jpg", "label": "Last Frame", "description": "Last video frame at 512px height. Frame index = total_frames - 1.", "type": "image"},
        {"filename": "sprite.jpg", "label": "Sprite Sheet", "description": "960x540 JPEG, 5x5 grid of 25 evenly-spaced frames at 192x108 contain-padded. Used for hover scrub. Frames via PyAV at np.linspace(0, total-1, 25).", "type": "image"},
        {"filename": "metadata.json", "label": "Video Metadata", "description": "JSON: {width (px), height (px), fps (float), num_frames (int), duration (s), file_size_mb (float)}.", "type": "data"},
    ]

    fields = {
        "width": {"label": "Width", "description": "Video width in pixels.", "dtype": "int"},
        "height": {"label": "Height", "description": "Video height in pixels.", "dtype": "int"},
        "fps": {"label": "FPS", "description": "Average frames per second.", "dtype": "float"},
        "num_frames": {"label": "Frame Count", "description": "Total video frames.", "dtype": "int"},
        "duration": {"label": "Duration (s)", "description": "Video duration in seconds = num_frames / fps.", "dtype": "float"},
        "file_size_mb": {"label": "File Size (MB)", "description": "Source MP4 file size in megabytes.", "dtype": "float"},
    }

    aggregation = [
        {"type": "json_dict", "source": "metadata.json", "target": "video_metadata.json"},
    ]

    preview_sections = [
        {"type": "side_by_side_images", "label": "Frames", "priority": 20,
         "description": "First, middle, and last frames extracted at 512px height (JPEG). Artifacts: thumb_first.jpg, thumb_middle.jpg, thumb_last.jpg.",
         "args": {"files": ["thumb_first.jpg", "thumb_middle.jpg", "thumb_last.jpg"],
                  "labels": ["First", "Middle", "Last"]}},
        {"type": "single_image", "label": "Sprite Sheet", "priority": 60,
         "description": "5x5 grid of 25 evenly-spaced frames from the video. Used for hover scrubbing in the grid view. Artifact: sprite.jpg.",
         "args": {"file": "sprite.jpg"}},
    ]

    def process(self, entries, dataset_dir, workers=DEFAULT_WORKERS):
        """Extract thumbnails + sprite + metadata for each video. CPU parallel."""
        global _processor_instance
        _processor_instance = self

        args = [(entry, dataset_dir) for entry in entries]
        run_pool_with_progress(_process_one, args, self.human_name, workers)


# ========================================================================
# Fire CLI
# ========================================================================

if __name__ == "__main__":
    fire.Fire({"main": IngestProcessor.cli_main})
