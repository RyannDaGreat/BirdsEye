"""
Profile ingest processor with:
1. Per-core CPU usage over time (saved as numpy array + plotted)
2. pyinstrument call tree for a single video
3. Breakdown: open vs decode vs resize vs save
"""

import time
import json
import os
import sys
import threading
import numpy as np
import psutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATASET_DIR = "datasets/pexels"
MANIFEST = "datasets/pexels/manifest.json"


def monitor_cpu(duration_sec, interval=0.5):
    """
    Record per-core CPU usage every interval seconds.
    Returns numpy array shape (num_samples, num_cores).
    """
    samples = []
    start = time.time()
    while time.time() - start < duration_sec:
        percents = psutil.cpu_percent(interval=interval, percpu=True)
        samples.append(percents)
    return np.array(samples)


def profile_single_video():
    """Profile a single video with pyinstrument + manual timing."""
    import pyinstrument
    from preprocess.video_utils import (
        sample_dir, ensure_sample_dir,
        resize_by_height, compose_sprite, resize_contain,
    )
    from decord import VideoReader, cpu
    from PIL import Image

    entries = json.load(open(MANIFEST))
    entry = entries[200]  # pick one we haven't processed
    sd = ensure_sample_dir(entry, DATASET_DIR)
    video_path = os.path.join(sd, "video.mp4")

    print(f"=== Single video profile: {entry['video_name']} ===")
    print(f"Source: {entry['source_path']}")

    # Clean existing artifacts
    for f in ['thumb_first.jpg', 'thumb_middle.jpg', 'thumb_last.jpg', 'sprite.jpg', 'metadata.json']:
        p = os.path.join(sd, f)
        if os.path.exists(p):
            os.remove(p)

    # Manual timing breakdown
    t0 = time.time()
    vr = VideoReader(video_path, ctx=cpu(0))
    t_open = time.time() - t0

    total = len(vr)
    fps = vr.get_avg_fps()
    h, w = vr[0].shape[:2]
    print(f"Video: {w}x{h}, {total} frames, {fps:.1f}fps")

    t0 = time.time()
    key_idx = [0, total // 2, max(0, total - 1)]
    sprite_idx = np.linspace(0, total - 1, 25, dtype=int).tolist()
    all_idx = sorted(set(key_idx + sprite_idx))
    frames = vr.get_batch(all_idx).asnumpy()
    t_decode = time.time() - t0

    t0 = time.time()
    index_map = {idx: i for i, idx in enumerate(all_idx)}
    key_images = {
        "first": Image.fromarray(frames[index_map[key_idx[0]]]),
        "middle": Image.fromarray(frames[index_map[key_idx[1]]]),
        "last": Image.fromarray(frames[index_map[key_idx[2]]]),
    }
    sprite_images = [Image.fromarray(frames[index_map[idx]]) for idx in sprite_idx]
    t_pil_convert = time.time() - t0

    t0 = time.time()
    for name, img in key_images.items():
        resized = resize_by_height(img, 512)
        resized.save(os.path.join(sd, f"thumb_{name}.jpg"), "JPEG", quality=30)
    t_thumb_save = time.time() - t0

    t0 = time.time()
    sprite = compose_sprite(sprite_images, 5, 5, 192, 108)
    sprite.save(os.path.join(sd, "sprite.jpg"), "JPEG", quality=80)
    t_sprite_save = time.time() - t0

    t0 = time.time()
    meta = {"width": int(w), "height": int(h), "fps": round(float(fps), 3),
            "num_frames": total, "duration": round(total / max(fps, 1e-6), 3),
            "file_size_mb": round(os.path.getsize(entry["source_path"]) / (1024*1024), 2)}
    with open(os.path.join(sd, "metadata.json"), "w") as f:
        json.dump(meta, f)
    t_meta_save = time.time() - t0

    total_time = t_open + t_decode + t_pil_convert + t_thumb_save + t_sprite_save + t_meta_save

    print(f"\n=== Timing Breakdown ===")
    print(f"  VideoReader open:   {t_open*1000:7.0f}ms  ({t_open/total_time*100:5.1f}%)")
    print(f"  Frame decode:       {t_decode*1000:7.0f}ms  ({t_decode/total_time*100:5.1f}%)")
    print(f"  PIL conversion:     {t_pil_convert*1000:7.0f}ms  ({t_pil_convert/total_time*100:5.1f}%)")
    print(f"  Thumbnail save:     {t_thumb_save*1000:7.0f}ms  ({t_thumb_save/total_time*100:5.1f}%)")
    print(f"  Sprite save:        {t_sprite_save*1000:7.0f}ms  ({t_sprite_save/total_time*100:5.1f}%)")
    print(f"  Metadata save:      {t_meta_save*1000:7.0f}ms  ({t_meta_save/total_time*100:5.1f}%)")
    print(f"  TOTAL:              {total_time*1000:7.0f}ms")

    # Now run pyinstrument
    print(f"\n=== pyinstrument profile (repeat) ===")
    # Clean again
    for f in ['thumb_first.jpg', 'thumb_middle.jpg', 'thumb_last.jpg', 'sprite.jpg', 'metadata.json']:
        p = os.path.join(sd, f)
        if os.path.exists(p):
            os.remove(p)

    profiler = pyinstrument.Profiler()
    profiler.start()

    from preprocess.processors.ingest import _process_one
    _process_one((entry, DATASET_DIR))

    profiler.stop()
    print(profiler.output_text(unicode=True, color=True))


def profile_batch_with_cpu_monitor():
    """Profile 50 videos while monitoring per-core CPU usage."""
    from multiprocessing import Pool
    from preprocess.processors.ingest import _process_one
    from preprocess.video_utils import sample_dir

    entries = json.load(open(MANIFEST))[300:350]  # 50 fresh videos

    # Clean
    for e in entries:
        sd = sample_dir(DATASET_DIR, e["video_name"])
        for f in ['thumb_first.jpg', 'thumb_middle.jpg', 'thumb_last.jpg', 'sprite.jpg', 'metadata.json']:
            p = os.path.join(sd, f)
            if os.path.exists(p):
                os.remove(p)

    print(f"\n=== Batch profile: 50 videos with Pool(32) + CPU monitor ===")

    # Start CPU monitor in background thread
    cpu_data = [None]
    monitor_done = threading.Event()

    def monitor_thread():
        cpu_data[0] = monitor_cpu(120, interval=1.0)  # max 2 minutes
        monitor_done.set()

    t = threading.Thread(target=monitor_thread, daemon=True)
    t.start()

    # Run the batch
    t0 = time.time()
    args = [(e, DATASET_DIR) for e in entries]
    with Pool(32) as pool:
        results = list(pool.imap_unordered(_process_one, args))
    elapsed = time.time() - t0

    # Wait for monitor to collect at least some data
    time.sleep(2)

    ok = sum(1 for _, s, _ in results if s)
    print(f"50 videos: {ok} ok in {elapsed:.1f}s = {ok/elapsed:.1f} videos/sec")

    # Save CPU data
    if cpu_data[0] is not None:
        arr = cpu_data[0]
        save_path = os.path.join("tests", "cpu_usage.npy")
        np.save(save_path, arr)
        print(f"\nCPU usage saved to {save_path}: shape {arr.shape}")
        print(f"  (rows=seconds, cols=cores)")

        # Print summary
        mean_per_core = arr.mean(axis=0)
        overall_mean = arr.mean()
        max_core = mean_per_core.max()
        print(f"  Overall mean CPU: {overall_mean:.1f}%")
        print(f"  Hottest core mean: {max_core:.1f}%")
        print(f"  Cores > 50% avg: {(mean_per_core > 50).sum()}/{len(mean_per_core)}")
        print(f"  Cores > 80% avg: {(mean_per_core > 80).sum()}/{len(mean_per_core)}")

        # Per-second overall usage
        per_sec = arr.mean(axis=1)
        print(f"  Per-second overall: min={per_sec.min():.1f}%, max={per_sec.max():.1f}%, mean={per_sec.mean():.1f}%")


if __name__ == "__main__":
    profile_single_video()
    profile_batch_with_cpu_monitor()
