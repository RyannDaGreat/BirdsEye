"""
Processor base class. All processors subclass this.

Shared helpers eliminate boilerplate across processor implementations:
  - run_pool_with_progress: Pool+tqdm+ok/fail loop for CPU processors
  - run_gpu_subprocess: subprocess launch for CUDA-isolated GPU processors
  - distribute_across_gpus: multi-GPU dispatch via torch.multiprocessing
  - Processor.cli_main: Fire CLI main() classmethod
"""

import os
import json
import tempfile
import subprocess as sp
from abc import ABC, abstractmethod
from multiprocessing import Pool

from tqdm import tqdm

from preprocess.video_utils import sample_dir, save_json_atomic


class Processor(ABC):
    """
    Base class for all video processors (plugins).

    ## Plugin Contract

    Every processor is ONE .py file in preprocess/processors/. Dropping a file
    here auto-registers it — no edits to __init__.py or process_all.py needed.

    ### Class requirements

    Subclasses MUST define:
        name: str           — e.g., "clip". Used in CLI flags (--process=clip, --skip=clip).
        human_name: str     — e.g., "CLIP Embeddings". Used in log messages.
        depends_on: list    — e.g., ["ingest"]. Processor names that must run first.
        artifacts: list     — [{filename, label, description, type}]. Files this processor creates
                              per sample. type is "image" or "data".
        fields: dict        — {field_name: {label, description, dtype}}. Numeric fields this
                              processor produces (for sort/filter/histogram in the UI).
                              dtype is "int" or "float" — controls slider precision in frontend.

    Subclasses MAY define:
        aggregation: list   — Rules for how per-sample data aggregates into cache/.
                              Two types supported:

                              json_dict: merge per-sample JSON into {video_name: data} dict
                                {"type": "json_dict", "source": "metadata.json",
                                 "target": "video_metadata.json"}

                              vector_index: read per-sample .npy, build FAISS IndexFlatIP
                                {"type": "vector_index", "source": "clip_embedding.npy",
                                 "prefix": "clip", "dim": 512}

                              Multiple processors can target the same json_dict file — their
                              values get merged per video. vector_index is per-processor; the
                              prefix must be unique across all processors.

    Subclasses MUST implement:
        process(entries, dataset_dir, workers) — process ONLY the given entries.

    ### Fire CLI requirement

    Every processor file MUST have a Fire CLI at the bottom using cli_main:

        if __name__ == "__main__":
            fire.Fire({"main": MyProcessor.cli_main})

    This allows:
        uv run python preprocess/processors/clip.py main --entries_json=... --dataset_dir=...

    GPU processors add additional Fire subcommands for subprocess isolation:

        if __name__ == "__main__":
            fire.Fire({"main": ClipProcessor.cli_main, "gpu_worker": gpu_worker})

    GPU processors use run_gpu_subprocess() in process() and
    distribute_across_gpus() in gpu_worker() to eliminate boilerplate.

    ### Artifact naming

    Artifact filenames should be prefixed with the processor concept:
        ingest:    thumb_first.jpg, thumb_middle.jpg, sprite.jpg, metadata.json
        clip:      clip_embedding.npy, clip_first.npy, clip_std.json
        raft_flow: flow_stats.json
        phash:     phash_stats.json

    ### Collision safety

    discover_processors() validates that no two processors share:
        - The same name
        - Any artifact filename
        - Any field name
        - Any vector_index prefix
    Violations raise ValueError at import time.
    """

    # --- Subclass must define these (enforced by __init_subclass__) ---
    name: str
    human_name: str
    depends_on: list = []
    artifacts: list = []     # [{filename, label, description, type}]
    fields: dict = {}        # {field_name: {label, description}}
    aggregation: list = []   # [{type, source, target/prefix, ...}]

    def __init_subclass__(cls, **kwargs):
        """Validate that subclasses define required class attributes."""
        super().__init_subclass__(**kwargs)
        # Skip validation for intermediate abstract subclasses
        if getattr(cls, '__abstractmethods__', None):
            return
        for attr in ("name", "human_name"):
            if not getattr(cls, attr, None):
                raise TypeError(
                    f"Processor subclass {cls.__name__} must define class attribute '{attr}'"
                )

    def needs_processing(self, sample_directory):
        """
        True if any artifact file is missing from this sample.

        Pure function.
        """
        for artifact in self.artifacts:
            if not os.path.exists(os.path.join(sample_directory, artifact["filename"])):
                return True
        return False

    def filter_todo(self, entries, dataset_dir):
        """
        Return only entries that need this processor's work.

        Pure function.
        """
        todo = []
        for entry in entries:
            sd = sample_dir(dataset_dir, entry["video_name"])
            if self.needs_processing(sd):
                todo.append(entry)
        return todo

    def ensure_sample_dir(self, entry, dataset_dir):
        """
        Create sample directory, write origins.json, create video.mp4 symlink.
        Returns the sample directory path.
        """
        sd = sample_dir(dataset_dir, entry["video_name"])
        os.makedirs(sd, exist_ok=True)

        origins_path = os.path.join(sd, "origins.json")
        if not os.path.exists(origins_path):
            save_json_atomic({
                "video_name": entry["video_name"],
                "caption": entry.get("caption", ""),
                "source_path": entry["source_path"],
                "dataset": os.path.basename(dataset_dir),
            }, origins_path)

        link_path = os.path.join(sd, "video.mp4")
        if not os.path.exists(link_path) and os.path.exists(entry["source_path"]):
            try:
                os.link(entry["source_path"], link_path)
            except OSError:
                os.symlink(os.path.abspath(entry["source_path"]), link_path)

        return sd

    @classmethod
    def cli_main(cls, entries_json, dataset_dir="datasets/pexels", workers=32):
        """
        Standalone CLI entry point for any processor.

        Usage (in processor file):
            if __name__ == "__main__":
                fire.Fire({"main": MyProcessor.cli_main})
        """
        with open(entries_json) as f:
            entries = json.load(f)
        proc = cls()
        proc.process(entries, dataset_dir, workers)

    @abstractmethod
    def process(self, entries, dataset_dir, workers=32):
        """
        Process ONLY the given entries. Nothing else.

        Subclass MUST implement.
        Must use tqdm for progress.
        Must call self.ensure_sample_dir for each entry.
        """


# ========================================================================
# Shared helpers — eliminate boilerplate across processors
# ========================================================================

def run_pool_with_progress(worker_fn, args, human_name, workers):
    """
    Run a worker function across args with Pool+tqdm, counting ok/fail results.

    worker_fn must return (name, success_bool, error_msg_or_None) tuples.
    Prints summary line on completion.

    >>> run_pool_with_progress(lambda x: (x, True, None), [], "Test", 1)
    (0, 0)
    """
    ok = fail = 0
    if not args:
        return ok, fail
    with Pool(workers) as pool:
        for name, success, err in tqdm(
            pool.imap_unordered(worker_fn, args),
            total=len(args), desc=f"  {human_name}",
        ):
            if success:
                ok += 1
            else:
                fail += 1
                if err:
                    tqdm.write(f"    FAIL {name}: {err}")
    print(f"  {human_name}: {ok} ok, {fail} failed")
    return ok, fail


def run_gpu_subprocess(entries, dataset_dir, script_file, human_name):
    """
    Launch a GPU worker as a subprocess for CUDA isolation.

    Writes sample list to temp JSON, calls the script's gpu_worker subcommand,
    cleans up, and raises on failure.

    Args:
        entries: list of entry dicts with video_name
        dataset_dir: dataset directory path
        script_file: __file__ of the calling processor module
        human_name: display name for log messages
    """
    sample_list = []
    for e in entries:
        sd = sample_dir(dataset_dir, e["video_name"])
        sample_list.append({"video_name": e["video_name"], "sample_dir": sd})

    fd, list_path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(sample_list, f)

    print(f"  {human_name}: processing {len(entries)} samples via subprocess...")
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(script_file))))
    result = sp.run(
        ["uv", "run", "python", script_file, "gpu_worker", "--list_path", list_path],
        cwd=repo_root,
    )

    os.unlink(list_path)
    if result.returncode != 0:
        raise RuntimeError(f"{human_name} subprocess exited with code {result.returncode}")


def distribute_across_gpus(label, samples, worker_fn, make_chunk_args=None):
    """
    Distribute samples across all available GPUs via torch.multiprocessing.Pool.

    Called from gpu_worker subprocess entry points. Handles spawn method,
    GPU count detection, chunking, and dispatch.

    Args:
        label: display name (e.g. "CLIP", "RAFT")
        samples: list of sample dicts loaded from JSON
        worker_fn: callable taking a single tuple arg, called per GPU chunk
        make_chunk_args: callable (gpu_id, chunk_samples) -> tuple for worker_fn.
                         Default: (gpu_id, chunk_samples)
    """
    import torch
    from torch.multiprocessing import Pool as TorchPool, set_start_method
    from datetime import datetime

    try:
        set_start_method("spawn")
    except RuntimeError:
        pass

    if make_chunk_args is None:
        make_chunk_args = lambda gpu_id, chunk: (gpu_id, chunk)

    num_gpus = torch.cuda.device_count() if torch.cuda.is_available() else 1
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] {label}: {len(samples)} samples across {num_gpus} GPUs", flush=True)

    chunks = []
    per_gpu = max(1, len(samples) // num_gpus)
    for g in range(num_gpus):
        s = g * per_gpu
        e = s + per_gpu if g < num_gpus - 1 else len(samples)
        if s < len(samples):
            chunks.append(make_chunk_args(g, samples[s:e]))

    if num_gpus > 1:
        with TorchPool(len(chunks)) as pool:
            pool.map(worker_fn, chunks)
    else:
        worker_fn(chunks[0])

    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] {label}: done, {len(samples)} samples processed", flush=True)


def make_gpu_logger(gpu_id):
    """Create a timestamped GPU logger closure. Returns callable(msg)."""
    from datetime import datetime
    def log(msg):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"  [{ts}] GPU {gpu_id}: {msg}", flush=True)
    return log
