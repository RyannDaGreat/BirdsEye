"""
Systematic benchmark for ingest processor performance.
Tests multiple approaches to find the fastest combination.

BULLDOG MODE: find the root cause of the 20-60x multiprocessing slowdown.

Approaches tested:
  A) decord2 + PIL (current)
  B) cv2 + cv2 (no PIL, no decord2)
  C) decord2 + cv2 (decord for decode, cv2 for resize/save)
  D) cv2 decode + cv2 save with ThreadPoolExecutor (thread-based)
  E) ProcessPoolExecutor vs multiprocessing.Pool

For each approach, test with worker counts: 1, 4, 8, 16, 32, 48, 64
"""

import time
import json
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATASET_DIR = "datasets/pexels"
MANIFEST = "datasets/pexels/manifest.json"

# Load entries
entries = json.load(open(MANIFEST))

# Constants matching ingest.py
THUMB_HEIGHT = 512
THUMB_QUALITY = 30
SPRITE_COLS = 5
SPRITE_ROWS = 5
SPRITE_CELL_W = 192
SPRITE_CELL_H = 108
NUM_SPRITE_FRAMES = SPRITE_COLS * SPRITE_ROWS  # 25

# ======================================================================
# Approach A: decord2 + PIL (current implementation)
# ======================================================================

def approach_a_decord_pil(video_path):
    """
    Current approach: decord2 for decode, PIL for resize/save.
    Returns time taken in seconds.
    """
    from decord import VideoReader, cpu
    from PIL import Image

    t0 = time.time()

    vr = VideoReader(video_path, ctx=cpu(0))
    total = len(vr)
    if total == 0:
        return time.time() - t0

    fps = vr.get_avg_fps()
    key_indices = [0, total // 2, max(0, total - 1)]
    sprite_indices = np.linspace(0, total - 1, NUM_SPRITE_FRAMES, dtype=int).tolist()
    all_indices = sorted(set(key_indices + sprite_indices))

    frames = vr.get_batch(all_indices).asnumpy()
    index_map = {idx: i for i, idx in enumerate(all_indices)}
    h, w = frames[0].shape[:2]

    # Convert to PIL
    key_images = {
        "first": Image.fromarray(frames[index_map[key_indices[0]]]),
        "middle": Image.fromarray(frames[index_map[key_indices[1]]]),
        "last": Image.fromarray(frames[index_map[key_indices[2]]]),
    }
    sprite_pil = [Image.fromarray(frames[index_map[idx]]) for idx in sprite_indices]

    # Resize thumbnails
    for name, img in key_images.items():
        ratio = THUMB_HEIGHT / img.height
        resized = img.resize((round(img.width * ratio), THUMB_HEIGHT), Image.LANCZOS)
        # Encode to JPEG in memory (don't save to disk to isolate CPU cost)
        import io
        buf = io.BytesIO()
        resized.save(buf, "JPEG", quality=THUMB_QUALITY)

    # Compose sprite
    sprite = Image.new("RGB", (SPRITE_COLS * SPRITE_CELL_W, SPRITE_ROWS * SPRITE_CELL_H), (0, 0, 0))
    for i, frame in enumerate(sprite_pil):
        if i >= SPRITE_COLS * SPRITE_ROWS:
            break
        frame_copy = frame.copy()
        frame_copy.thumbnail((SPRITE_CELL_W, SPRITE_CELL_H), Image.LANCZOS)
        padded = Image.new("RGB", (SPRITE_CELL_W, SPRITE_CELL_H), (0, 0, 0))
        padded.paste(frame_copy, ((SPRITE_CELL_W - frame_copy.width) // 2, (SPRITE_CELL_H - frame_copy.height) // 2))
        row, col = divmod(i, SPRITE_COLS)
        sprite.paste(padded, (col * SPRITE_CELL_W, row * SPRITE_CELL_H))

    buf = io.BytesIO()
    sprite.save(buf, "JPEG", quality=80)

    return time.time() - t0


# ======================================================================
# Approach B: cv2 only (no decord, no PIL)
# ======================================================================

def approach_b_cv2_only(video_path):
    """
    Pure cv2 approach: cv2.VideoCapture for decode, cv2 for resize/save.
    Seeks to specific frames instead of reading sequentially.
    """
    import cv2

    t0 = time.time()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return time.time() - t0

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if total == 0:
        cap.release()
        return time.time() - t0

    key_indices = [0, total // 2, max(0, total - 1)]
    sprite_indices = np.linspace(0, total - 1, NUM_SPRITE_FRAMES, dtype=int).tolist()
    all_indices = sorted(set(key_indices + sprite_indices))

    # Read all needed frames by seeking
    frames = {}
    for idx in all_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret:
            frames[idx] = frame  # BGR numpy array
    cap.release()

    if not frames:
        return time.time() - t0

    # Resize thumbnails (cv2)
    for ki in key_indices:
        if ki not in frames:
            continue
        frame = frames[ki]
        ratio = THUMB_HEIGHT / frame.shape[0]
        new_w = round(frame.shape[1] * ratio)
        resized = cv2.resize(frame, (new_w, THUMB_HEIGHT), interpolation=cv2.INTER_LANCZOS4)
        # Encode to JPEG in memory
        cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, THUMB_QUALITY])

    # Compose sprite (cv2) — create black canvas, paste resized frames
    sprite = np.zeros((SPRITE_ROWS * SPRITE_CELL_H, SPRITE_COLS * SPRITE_CELL_W, 3), dtype=np.uint8)
    for i, idx in enumerate(sprite_indices):
        if i >= SPRITE_COLS * SPRITE_ROWS or idx not in frames:
            continue
        frame = frames[idx]
        # Contain-fit resize
        fh, fw = frame.shape[:2]
        scale = min(SPRITE_CELL_W / fw, SPRITE_CELL_H / fh)
        new_w = round(fw * scale)
        new_h = round(fh * scale)
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        # Center paste
        row, col = divmod(i, SPRITE_COLS)
        y_off = row * SPRITE_CELL_H + (SPRITE_CELL_H - new_h) // 2
        x_off = col * SPRITE_CELL_W + (SPRITE_CELL_W - new_w) // 2
        sprite[y_off:y_off + new_h, x_off:x_off + new_w] = resized

    cv2.imencode('.jpg', sprite, [cv2.IMWRITE_JPEG_QUALITY, 80])

    return time.time() - t0


# ======================================================================
# Approach C: decord2 decode + cv2 resize/save (hybrid)
# ======================================================================

def approach_c_decord_cv2(video_path):
    """
    Hybrid: decord2 for fast batch decode, cv2 for resize/encode.
    No PIL at all.
    """
    from decord import VideoReader, cpu
    import cv2

    t0 = time.time()

    vr = VideoReader(video_path, ctx=cpu(0))
    total = len(vr)
    if total == 0:
        return time.time() - t0

    fps = vr.get_avg_fps()
    key_indices = [0, total // 2, max(0, total - 1)]
    sprite_indices = np.linspace(0, total - 1, NUM_SPRITE_FRAMES, dtype=int).tolist()
    all_indices = sorted(set(key_indices + sprite_indices))

    # Batch decode (decord2's strength)
    all_frames = vr.get_batch(all_indices).asnumpy()  # RGB numpy
    index_map = {idx: i for i, idx in enumerate(all_indices)}
    h, w = all_frames[0].shape[:2]

    # Thumbnails via cv2 (frames are RGB, cv2 wants BGR for imencode)
    for ki in key_indices:
        frame_rgb = all_frames[index_map[ki]]
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        ratio = THUMB_HEIGHT / frame_bgr.shape[0]
        new_w = round(frame_bgr.shape[1] * ratio)
        resized = cv2.resize(frame_bgr, (new_w, THUMB_HEIGHT), interpolation=cv2.INTER_LANCZOS4)
        cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, THUMB_QUALITY])

    # Sprite via cv2
    sprite = np.zeros((SPRITE_ROWS * SPRITE_CELL_H, SPRITE_COLS * SPRITE_CELL_W, 3), dtype=np.uint8)
    for i, idx in enumerate(sprite_indices):
        if i >= SPRITE_COLS * SPRITE_ROWS:
            break
        frame_rgb = all_frames[index_map[idx]]
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        fh, fw = frame_bgr.shape[:2]
        scale = min(SPRITE_CELL_W / fw, SPRITE_CELL_H / fh)
        new_w = round(fw * scale)
        new_h = round(fh * scale)
        resized = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        row, col = divmod(i, SPRITE_COLS)
        y_off = row * SPRITE_CELL_H + (SPRITE_CELL_H - new_h) // 2
        x_off = col * SPRITE_CELL_W + (SPRITE_CELL_W - new_w) // 2
        sprite[y_off:y_off + new_h, x_off:x_off + new_w] = resized

    cv2.imencode('.jpg', sprite, [cv2.IMWRITE_JPEG_QUALITY, 80])

    return time.time() - t0


# ======================================================================
# Worker wrappers for multiprocessing Pool
# ======================================================================

def _worker_a(video_path):
    """Wrapper for Pool: decord+PIL."""
    t = approach_a_decord_pil(video_path)
    return (video_path, t)

def _worker_b(video_path):
    """Wrapper for Pool: cv2 only."""
    t = approach_b_cv2_only(video_path)
    return (video_path, t)

def _worker_c(video_path):
    """Wrapper for Pool: decord+cv2."""
    t = approach_c_decord_cv2(video_path)
    return (video_path, t)


# ======================================================================
# Benchmark runner
# ======================================================================

def run_benchmark(approach_fn, video_paths, num_workers, label):
    """
    Run approach_fn on video_paths with num_workers.
    Returns (total_time, per_video_times, throughput).
    """
    from multiprocessing import Pool

    print(f"\n  {label} | workers={num_workers} | videos={len(video_paths)}")

    t0 = time.time()
    per_video_times = []

    if num_workers <= 1:
        # Serial
        for vp in video_paths:
            _, t = approach_fn(vp)
            per_video_times.append(t)
    else:
        with Pool(num_workers) as pool:
            for vp, t in pool.imap_unordered(approach_fn, video_paths):
                per_video_times.append(t)

    total = time.time() - t0
    throughput = len(video_paths) / total
    times = np.array(per_video_times)

    print(f"    Total: {total:.1f}s | Throughput: {throughput:.1f} vid/s")
    print(f"    Per-video: mean={times.mean():.2f}s median={np.median(times):.2f}s max={times.max():.2f}s min={times.min():.2f}s")

    return total, per_video_times, throughput


def main():
    import fire

    def benchmark(n_videos=100, worker_counts="1,4,8,16,32,48", approaches="a,b,c"):
        """
        Run benchmark with multiple approaches and worker counts.

        Args:
            n_videos: Number of videos to test with
            worker_counts: Comma-separated worker counts
            approaches: Comma-separated approach letters (a=decord+pil, b=cv2, c=decord+cv2)
        """
        # Fire passes tuples for comma-separated args, or strings
        if isinstance(worker_counts, (list, tuple)):
            workers = [int(x) for x in worker_counts]
        else:
            workers = [int(x) for x in str(worker_counts).split(",")]
        if isinstance(approaches, (list, tuple)):
            approach_list = [str(x).strip() for x in approaches]
        else:
            approach_list = [x.strip() for x in str(approaches).split(",")]

        approach_map = {
            "a": (_worker_a, "decord2+PIL"),
            "b": (_worker_b, "cv2-only"),
            "c": (_worker_c, "decord2+cv2"),
        }

        # Get video paths from manifest
        from preprocess.video_utils import sample_dir, ensure_sample_dir

        # Use entries that already have video.mp4 links
        selected = entries[:n_videos]
        video_paths = []
        for entry in selected:
            sd = sample_dir(DATASET_DIR, entry["video_name"])
            vp = os.path.join(sd, "video.mp4")
            # If sample dir doesn't exist yet, try the source path directly
            if not os.path.exists(vp):
                vp = entry["source_path"]
            if os.path.exists(vp):
                video_paths.append(vp)

        print(f"{'='*70}")
        print(f"INGEST PERFORMANCE BENCHMARK")
        print(f"{'='*70}")
        print(f"Videos: {len(video_paths)}")
        print(f"Worker counts: {workers}")
        print(f"Approaches: {approach_list}")
        print(f"CPUs: {os.cpu_count()}")
        print(f"{'='*70}")

        results = {}

        for approach_key in approach_list:
            if approach_key not in approach_map:
                print(f"Unknown approach: {approach_key}")
                continue

            fn, label = approach_map[approach_key]
            print(f"\n{'='*70}")
            print(f"APPROACH {approach_key.upper()}: {label}")
            print(f"{'='*70}")

            results[approach_key] = {}

            for nw in workers:
                total, times, throughput = run_benchmark(fn, video_paths, nw, label)
                results[approach_key][nw] = {
                    "total": total,
                    "throughput": throughput,
                    "mean": float(np.mean(times)),
                    "median": float(np.median(times)),
                    "max": float(np.max(times)),
                    "min": float(np.min(times)),
                }

        # Summary table
        print(f"\n{'='*70}")
        print(f"SUMMARY: Throughput (videos/sec)")
        print(f"{'='*70}")
        print(f"{'Approach':<20}", end="")
        for nw in workers:
            print(f"{'w='+str(nw):>10}", end="")
        print()
        print("-" * (20 + 10 * len(workers)))

        for approach_key in approach_list:
            if approach_key not in results:
                continue
            _, label = approach_map[approach_key]
            print(f"{label:<20}", end="")
            for nw in workers:
                if nw in results[approach_key]:
                    tp = results[approach_key][nw]["throughput"]
                    print(f"{tp:>10.1f}", end="")
                else:
                    print(f"{'N/A':>10}", end="")
            print()

        print(f"\n{'='*70}")
        print(f"SUMMARY: Per-video mean time (seconds)")
        print(f"{'='*70}")
        print(f"{'Approach':<20}", end="")
        for nw in workers:
            print(f"{'w='+str(nw):>10}", end="")
        print()
        print("-" * (20 + 10 * len(workers)))

        for approach_key in approach_list:
            if approach_key not in results:
                continue
            _, label = approach_map[approach_key]
            print(f"{label:<20}", end="")
            for nw in workers:
                if nw in results[approach_key]:
                    mt = results[approach_key][nw]["mean"]
                    print(f"{mt:>10.2f}", end="")
                else:
                    print(f"{'N/A':>10}", end="")
            print()

        # Save results
        save_path = os.path.join("tests", "benchmark_results.json")
        with open(save_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {save_path}")

    fire.Fire(benchmark)


if __name__ == "__main__":
    main()
