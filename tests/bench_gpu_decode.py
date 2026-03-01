"""
Benchmark: PyNvVideoCodec GPU decode vs PyAV CPU decode.
Full pipeline: decode + resize + JPEG encode.
Tests scaling across multiple GPUs.
"""
import time, json, os, sys, subprocess
import numpy as np
import cv2
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from multiprocessing import Pool

sys.path.insert(0, '/root/miniconda3/envs/LTX2/lib/python3.12/site-packages')

THUMB_HEIGHT = 512
SPRITE_CELL_W = 192
SPRITE_CELL_H = 108


def select_videos(manifest_path="datasets/pexels/manifest.json", n=200):
    """Select n representative videos evenly from manifest. Pure function."""
    entries = json.load(open(manifest_path))
    step = max(1, len(entries) // n)
    selected = entries[::step][:n]
    valid = [e for e in selected if os.path.exists(e["source_path"])]
    sizes = [os.path.getsize(e["source_path"]) / 1024 / 1024 for e in valid]
    print(f"Selected {len(valid)} videos from {len(entries)} total")
    print(f"File sizes: mean={np.mean(sizes):.0f}MB, median={np.median(sizes):.0f}MB, max={np.max(sizes):.0f}MB")
    return valid


def process_gpu_single(args):
    """Full pipeline using PyNvVideoCodec on assigned GPU."""
    video_path, gpu_id = args
    import torch
    from PyNvVideoCodec import SimpleDecoder, OutputColorType

    t0 = time.time()

    decoder = SimpleDecoder(video_path, gpu_id=gpu_id, output_color_type=OutputColorType.RGBP)
    total = len(decoder)
    if total == 0:
        return time.time() - t0

    # Frame indices
    key_indices = [0, total // 2, max(0, total - 1)]
    sprite_indices = np.linspace(0, total - 1, 25, dtype=int).tolist()
    all_indices = sorted(set(key_indices + sprite_indices))

    # GPU decode
    frames = decoder.get_batch_frames_by_index(all_indices)

    # GPU -> CPU transfer + format conversion (RGBP C,H,W -> HWC BGR)
    index_map = {idx: i for i, idx in enumerate(all_indices)}
    numpy_frames = {}
    for orig_idx, pos in index_map.items():
        tensor = torch.from_dlpack(frames[pos])
        # RGBP: (3, H, W) -> transpose to (H, W, 3) then RGB->BGR
        arr = tensor.cpu().numpy()
        arr = np.transpose(arr, (1, 2, 0))  # C,H,W -> H,W,C
        arr = arr[:, :, ::-1].copy()  # RGB -> BGR
        numpy_frames[orig_idx] = arr

    # Thumbnails: resize to 512px height + JPEG encode
    for ki in key_indices:
        if ki in numpy_frames:
            f = numpy_frames[ki]
            h, w = f.shape[:2]
            ratio = THUMB_HEIGHT / h
            nw = round(w * ratio)
            r = cv2.resize(f, (nw, THUMB_HEIGHT), interpolation=cv2.INTER_AREA)
            cv2.imencode('.jpg', r, [cv2.IMWRITE_JPEG_QUALITY, 30])

    # Sprite: resize to 192x108, compose into 5x5 grid, JPEG encode
    sprite = np.zeros((5 * SPRITE_CELL_H, 5 * SPRITE_CELL_W, 3), dtype=np.uint8)
    for i, idx in enumerate(sprite_indices):
        if i >= 25 or idx not in numpy_frames:
            continue
        f = numpy_frames[idx]
        fh, fw = f.shape[:2]
        sc = min(SPRITE_CELL_W / fw, SPRITE_CELL_H / fh)
        nw, nh = round(fw * sc), round(fh * sc)
        r = cv2.resize(f, (nw, nh), interpolation=cv2.INTER_AREA)
        row, col = divmod(i, 5)
        yo, xo = row * SPRITE_CELL_H + (SPRITE_CELL_H - nh) // 2, col * SPRITE_CELL_W + (SPRITE_CELL_W - nw) // 2
        sprite[yo:yo + nh, xo:xo + nw] = r
    cv2.imencode('.jpg', sprite, [cv2.IMWRITE_JPEG_QUALITY, 80])

    del decoder
    return time.time() - t0


def process_cpu_pyav(args):
    """Full pipeline using PyAV CPU decode."""
    video_path, _ = args
    import av

    t0 = time.time()
    container = av.open(video_path)
    stream = container.streams.video[0]
    stream.thread_type = 'AUTO'

    total = stream.frames
    if total == 0:
        dur = container.duration
        if dur:
            fps = float(stream.average_rate) if stream.average_rate else 30
            total = int(dur / 1_000_000 * fps)
    if total == 0:
        container.close()
        return time.time() - t0

    key_indices = [0, total // 2, max(0, total - 1)]
    sprite_indices = np.linspace(0, total - 1, 25, dtype=int).tolist()
    all_needed = set(key_indices + sprite_indices)
    max_needed = max(all_needed)

    frames = {}
    n = 0
    for frame in container.decode(video=0):
        if n in all_needed:
            frames[n] = frame.to_ndarray(format='bgr24')
        n += 1
        if n > max_needed:
            break
    container.close()

    if not frames:
        return time.time() - t0

    # Thumbnails
    for ki in key_indices:
        if ki not in frames:
            continue
        f = frames[ki]
        ratio = THUMB_HEIGHT / f.shape[0]
        nw = round(f.shape[1] * ratio)
        r = cv2.resize(f, (nw, THUMB_HEIGHT), interpolation=cv2.INTER_AREA)
        cv2.imencode('.jpg', r, [cv2.IMWRITE_JPEG_QUALITY, 30])

    # Sprite
    sprite = np.zeros((5 * SPRITE_CELL_H, 5 * SPRITE_CELL_W, 3), dtype=np.uint8)
    for i, idx in enumerate(sprite_indices):
        if i >= 25 or idx not in frames:
            continue
        f = frames[idx]
        fh, fw = f.shape[:2]
        sc = min(SPRITE_CELL_W / fw, SPRITE_CELL_H / fh)
        nw, nh = round(fw * sc), round(fh * sc)
        r = cv2.resize(f, (nw, nh), interpolation=cv2.INTER_AREA)
        row, col = divmod(i, 5)
        yo, xo = row * SPRITE_CELL_H + (SPRITE_CELL_H - nh) // 2, col * SPRITE_CELL_W + (SPRITE_CELL_W - nw) // 2
        sprite[yo:yo + nh, xo:xo + nw] = r
    cv2.imencode('.jpg', sprite, [cv2.IMWRITE_JPEG_QUALITY, 80])

    return time.time() - t0


def main():
    # Count GPUs
    gpu_count = int(subprocess.run(['nvidia-smi', '-L'], capture_output=True, text=True).stdout.count('GPU'))
    print(f"GPUs: {gpu_count}")

    entries = select_videos(n=200)
    paths = [e["source_path"] for e in entries]
    print(f"Videos: {len(paths)}")

    print()
    print("=" * 70)
    print("GPU DECODE (PyNvVideoCodec) vs CPU DECODE (PyAV)")
    print("=" * 70)

    # ---- Single video timing ----
    print("\n--- Single video timing ---")
    t0 = time.time()
    dt = process_gpu_single((paths[0], 0))
    print(f"GPU single: {dt*1000:.0f}ms (wall: {(time.time()-t0)*1000:.0f}ms)")

    t0 = time.time()
    dt = process_cpu_pyav((paths[0], 0))
    print(f"CPU single: {dt*1000:.0f}ms (wall: {(time.time()-t0)*1000:.0f}ms)")

    # ---- GPU decode with ThreadPoolExecutor (GIL-released in C++) ----
    print("\n--- GPU decode (ThreadPoolExecutor, round-robin GPUs) ---")
    for nw in [gpu_count, gpu_count * 2, gpu_count * 3, gpu_count * 4]:
        args = [(p, i % gpu_count) for i, p in enumerate(paths)]
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=nw) as executor:
            times = list(executor.map(process_gpu_single, args))
        wall = time.time() - t0
        tp = len(paths) / wall
        print(f"GPU threads={nw:>3} | {tp:.1f} vid/s | wall={wall:.1f}s | mean={np.mean(times):.2f}s max={np.max(times):.1f}s")

    # ---- GPU decode with Pool (process isolation) ----
    print("\n--- GPU decode (multiprocessing.Pool, round-robin GPUs) ---")
    for nw in [gpu_count, gpu_count * 2]:
        args = [(p, i % gpu_count) for i, p in enumerate(paths)]
        t0 = time.time()
        with Pool(nw) as pool:
            times = list(pool.imap_unordered(process_gpu_single, args))
        wall = time.time() - t0
        tp = len(paths) / wall
        print(f"GPU procs={nw:>3}  | {tp:.1f} vid/s | wall={wall:.1f}s | mean={np.mean(times):.2f}s max={np.max(times):.1f}s")

    # ---- CPU baseline ----
    print("\n--- CPU decode (PyAV, multiprocessing.Pool) ---")
    for nw in [16]:
        args = [(p, 0) for p in paths]
        t0 = time.time()
        with Pool(nw) as pool:
            times = list(pool.imap_unordered(process_cpu_pyav, args))
        wall = time.time() - t0
        tp = len(paths) / wall
        print(f"CPU procs={nw:>3}  | {tp:.1f} vid/s | wall={wall:.1f}s | mean={np.mean(times):.2f}s max={np.max(times):.1f}s")


if __name__ == "__main__":
    main()
