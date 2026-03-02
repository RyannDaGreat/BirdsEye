"""
Benchmark: PyNvVideoCodec GPU decode via subprocess isolation.
Each worker process creates exactly ONE decoder, processes ONE video, and exits.
This works around the PyNvVideoCodec decoder lifecycle crash.
"""
import time, json, os, sys, subprocess, tempfile, struct
import numpy as np
import cv2
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Pool

THUMB_HEIGHT = 512
SPRITE_CELL_W = 192
SPRITE_CELL_H = 108


def select_videos(manifest_path="datasets/pexels/manifest.json", n=200):
    """Select n representative videos. Pure function."""
    entries = json.load(open(manifest_path))
    step = max(1, len(entries) // n)
    selected = entries[::step][:n]
    return [e for e in selected if os.path.exists(e["source_path"])]


def gpu_worker_single(args):
    """Process ONE video using PyNvVideoCodec in current process (no reuse)."""
    video_path, gpu_id = args
    import torch
    from PyNvVideoCodec import SimpleDecoder, OutputColorType

    t0 = time.time()
    decoder = SimpleDecoder(video_path, gpu_id=gpu_id, output_color_type=OutputColorType.RGBP)
    total = len(decoder)
    if total == 0:
        return time.time() - t0

    key_indices = [0, total // 2, max(0, total - 1)]
    sprite_indices = np.linspace(0, total - 1, 25, dtype=int).tolist()
    all_indices = sorted(set(key_indices + sprite_indices))

    frames = decoder.get_batch_frames_by_index(all_indices)

    index_map = {idx: i for i, idx in enumerate(all_indices)}
    numpy_frames = {}
    for orig_idx, pos in index_map.items():
        tensor = torch.from_dlpack(frames[pos])
        arr = tensor.cpu().numpy()
        arr = np.transpose(arr, (1, 2, 0))
        arr = arr[:, :, ::-1].copy()
        numpy_frames[orig_idx] = arr

    for ki in key_indices:
        if ki in numpy_frames:
            f = numpy_frames[ki]
            h, w = f.shape[:2]
            ratio = THUMB_HEIGHT / h
            nw = round(w * ratio)
            r = cv2.resize(f, (nw, THUMB_HEIGHT), interpolation=cv2.INTER_AREA)
            cv2.imencode('.jpg', r, [cv2.IMWRITE_JPEG_QUALITY, 30])

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


def cpu_worker(args):
    """Process ONE video using PyAV CPU decode."""
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

    for ki in key_indices:
        if ki not in frames:
            continue
        f = frames[ki]
        ratio = THUMB_HEIGHT / f.shape[0]
        nw = round(f.shape[1] * ratio)
        r = cv2.resize(f, (nw, THUMB_HEIGHT), interpolation=cv2.INTER_AREA)
        cv2.imencode('.jpg', r, [cv2.IMWRITE_JPEG_QUALITY, 30])

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


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.set_start_method('spawn', force=True)

    gpu_count = int(subprocess.run(['nvidia-smi', '-L'], capture_output=True, text=True).stdout.count('GPU'))
    print(f"GPUs: {gpu_count}")

    os.chdir('/root/CleanCode/Dumps/Searchable_Pexels_v2')
    entries = select_videos(n=200)
    paths = [e["source_path"] for e in entries]
    print(f"Videos: {len(paths)}")

    print()
    print("=" * 70)
    print("GPU (PyNvVideoCodec subprocess) vs CPU (PyAV multiprocessing)")
    print("=" * 70)

    # GPU with Pool (each worker dies after maxtasksperchild=1)
    print("\n--- GPU decode with maxtasksperchild=1 (fresh process per video) ---")
    for nw in [16, 32, 48, 64]:
        args = [(p, i % gpu_count) for i, p in enumerate(paths)]
        t0 = time.time()
        with Pool(nw, maxtasksperchild=1) as pool:
            results = []
            for r in pool.imap_unordered(gpu_worker_single, args):
                results.append(r)
        wall = time.time() - t0
        tp = len(paths) / wall
        times = [r for r in results if r is not None]
        print(f"GPU workers={nw:>3} mtpc=1 | {tp:.1f} vid/s | wall={wall:.1f}s | n={len(times)}")

    # GPU with Pool (workers process multiple videos)
    print("\n--- GPU decode with maxtasksperchild=3 ---")
    for nw in [16, 32, 48]:
        args = [(p, i % gpu_count) for i, p in enumerate(paths)]
        t0 = time.time()
        with Pool(nw, maxtasksperchild=3) as pool:
            results = list(pool.imap_unordered(gpu_worker_single, args))
        wall = time.time() - t0
        tp = len(paths) / wall
        times = [r for r in results if r is not None]
        print(f"GPU workers={nw:>3} mtpc=3 | {tp:.1f} vid/s | wall={wall:.1f}s | n={len(times)}")

    # CPU baseline
    print("\n--- CPU decode (PyAV) ---")
    for nw in [16]:
        args = [(p, 0) for p in paths]
        t0 = time.time()
        with Pool(nw) as pool:
            results = list(pool.imap_unordered(cpu_worker, args))
        wall = time.time() - t0
        tp = len(paths) / wall
        print(f"CPU workers={nw:>3}         | {tp:.1f} vid/s | wall={wall:.1f}s")
