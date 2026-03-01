"""
Benchmark: PyAV+cv2 ingest processor with actual disk saves.
Tests various worker counts to find optimal throughput.
"""
import time, json, os, sys, shutil, tempfile
import numpy as np
from multiprocessing import Pool
import fire

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def select_videos(manifest_path, n=200):
    """Select n representative videos evenly from manifest. Pure function."""
    entries = json.load(open(manifest_path))
    step = max(1, len(entries) // n)
    selected = entries[::step][:n]
    valid = [e for e in selected if os.path.exists(e["source_path"])]
    sizes = [os.path.getsize(e["source_path"]) / 1024 / 1024 for e in valid]
    print(f"Selected {len(valid)} videos from {len(entries)} total (step={step})")
    print(f"File sizes: mean={np.mean(sizes):.0f}MB, median={np.median(sizes):.0f}MB, max={np.max(sizes):.0f}MB")
    return valid


def benchmark_ingest(manifest="datasets/pexels/manifest.json", n=200,
                     worker_counts="8,12,16,20,24", output_dir=None):
    """
    Benchmark the PyAV+cv2 ingest processor with actual disk saves.

    Args:
        manifest: Path to manifest.json
        n: Number of videos to process
        worker_counts: Comma-separated worker counts to test
        output_dir: Where to write sample artifacts (temp dir if None)
    """
    from preprocess.video_utils import ensure_sample_dir
    from preprocess.processors.ingest import _process_one

    if isinstance(worker_counts, str):
        wc_list = [int(x) for x in worker_counts.split(",")]
    elif isinstance(worker_counts, (list, tuple)):
        wc_list = [int(x) for x in worker_counts]
    else:
        wc_list = [int(worker_counts)]

    entries = select_videos(manifest, n)

    use_temp = output_dir is None
    if use_temp:
        output_dir = tempfile.mkdtemp(prefix="bench_ingest_")
        print(f"Using temp dir: {output_dir}")

    print()
    print("=" * 70)
    print(f"PyAV+cv2 INGEST BENCHMARK ({len(entries)} videos, actual disk saves)")
    print("=" * 70)
    print(f"{'workers':>8} {'vid/s':>8} {'wall':>8} {'mean':>8} {'max':>8}")
    print("-" * 50)

    for nw in wc_list:
        # Clean output dir between runs
        if os.path.exists(os.path.join(output_dir, "samples")):
            shutil.rmtree(os.path.join(output_dir, "samples"))

        args = [(entry, output_dir) for entry in entries]
        t0 = time.time()
        with Pool(nw) as pool:
            results = list(pool.imap_unordered(_process_one, args))
        wall = time.time() - t0

        ok = sum(1 for _, s, _ in results if s)
        fail = sum(1 for _, s, _ in results if not s)
        tp = len(entries) / wall

        print(f"{nw:>8} {tp:>8.1f} {wall:>8.1f}s {'':>8} {'':>8}  ({ok} ok, {fail} fail)")

        # Print failures
        for name, success, err in results:
            if not success and err:
                print(f"         FAIL {name}: {err}")

    # Count files produced
    artifact_count = 0
    for root, dirs, files in os.walk(os.path.join(output_dir, "samples")):
        artifact_count += len(files)
    print(f"\nTotal artifacts written: {artifact_count}")

    if use_temp:
        print(f"Cleaning up: {output_dir}")
        shutil.rmtree(output_dir)


if __name__ == "__main__":
    fire.Fire(benchmark_ingest)
