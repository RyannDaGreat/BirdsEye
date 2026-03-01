"""
Video processing pipeline with modular processor system.

Discovers processors from preprocess/processors/, resolves dependencies,
processes videos in batches. Each processor only touches its batch.

Features:
  - Auto-discovers processors from preprocess/processors/
  - Dependency resolution (--process=ingest auto-enables compress)
  - Prerequisite priority sorting: after shuffle, stable-sort by # of processors
    whose dependencies are already satisfied (descending). Ready-to-run videos first.
  - Auto-aggregation: runs aggregator after each batch so server picks up new data.

Usage:
    uv run python preprocess/process_all.py
    uv run python preprocess/process_all.py --process=ingest,phash --batch_size=500
    uv run python preprocess/process_all.py --skip=clip,raft_flow --batch_size=500 --shuffle
"""

import json
import os
import sys
import time
import random
from collections import Counter
from datetime import datetime

import fire

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from preprocess.processors import discover_processors, resolve_dependencies
from preprocess.video_utils import sample_dir


DATASETS_ROOT = os.path.join(REPO_ROOT, "datasets")


def _log(msg):
    """
    Print a timestamped log message.

    >>> _log("test")  # doctest: +SKIP
    [12:34:56] test
    """
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _parse_name_list(value, valid_names, flag_name):
    """
    Parse a comma-separated processor name list. Exits on unknown names.

    Accepts: "ingest,phash" or ["ingest", "phash"] (Fire handles both).
    Validates all names exist.

    >>> _parse_name_list("a,b", ["a", "b", "c"], "--process")
    ['a', 'b']
    >>> _parse_name_list(["a"], ["a", "b"], "--process")
    ['a']
    """
    if isinstance(value, str):
        names = [n.strip() for n in value.split(",") if n.strip()]
    elif isinstance(value, (list, tuple)):
        names = list(value)
    else:
        names = [str(value)]

    for n in names:
        if n not in valid_names:
            print(f"ERROR: Unknown processor '{n}' in {flag_name}")
            print(f"Valid: {valid_names}")
            sys.exit(1)
    return names


def count_satisfied_deps(sample_directory, ordered_processors, all_processors):
    """
    Count how many of the ordered processors have ALL dependency artifacts present.
    Pure function.

    A processor's dependencies are "satisfied" if every artifact of every dependency
    processor already exists in the sample directory. A root processor (no deps) always
    counts as having satisfied dependencies.

    Args:
        sample_directory: path to the sample's artifact directory
        ordered_processors: list of processor names in dependency order
        all_processors: dict {name: Processor} of all discovered processors

    Returns:
        int — number of processors whose prerequisites are fully satisfied

    >>> class FakeProc:
    ...     def __init__(self, name, deps, artifacts):
    ...         self.name = name
    ...         self.depends_on = deps
    ...         self.artifacts = [{"filename": a} for a in artifacts]
    >>> procs = {
    ...     "a": FakeProc("a", [], ["a.txt"]),
    ...     "b": FakeProc("b", ["a"], ["b.txt"]),
    ...     "c": FakeProc("c", ["b"], ["c.txt"]),
    ... }
    >>> count_satisfied_deps("/nonexistent", ["a", "b", "c"], procs)
    1
    """
    count = 0
    for pname in ordered_processors:
        proc = all_processors[pname]
        if not proc.depends_on:
            # Root processor — deps trivially satisfied
            count += 1
            continue
        all_deps_satisfied = True
        for dep_name in proc.depends_on:
            dep = all_processors[dep_name]
            for artifact in dep.artifacts:
                path = os.path.join(sample_directory, artifact["filename"])
                if not os.path.exists(path):
                    all_deps_satisfied = False
                    break
            if not all_deps_satisfied:
                break
        if all_deps_satisfied:
            count += 1
    return count


def format_tier_breakdown(tier_counts, num_processors):
    """
    Format a tier breakdown string for display. Pure function.

    Args:
        tier_counts: Counter mapping tier (int) → count of videos
        num_processors: total number of enabled processors (max possible tier)

    Returns:
        str with one line per tier

    >>> format_tier_breakdown(Counter({3: 100, 1: 50, 0: 25}), 3)
    '    Tier 3/3 (all deps ready):           100 videos\\n    Tier 1/3:                             50 videos\\n    Tier 0/3 (nothing ready):             25 videos'
    """
    lines = []
    for tier in sorted(tier_counts.keys(), reverse=True):
        count = tier_counts[tier]
        label = f"Tier {tier}/{num_processors}"
        if tier == num_processors:
            label += " (all deps ready)"
        elif tier == 0:
            label += " (nothing ready)"
        lines.append(f"    {label + ':':<34}{count:>6} videos")
    return "\n".join(lines)


def priority_sort(todo, dataset_dir, ordered, all_processors):
    """
    Stable-sort videos by prerequisite readiness (descending). Pure function.

    After this sort, videos whose dependencies are most satisfied appear first.
    Because Python's sort is stable, the pre-sort order (shuffled for multi-machine
    safety) is preserved within each tier.

    Args:
        todo: list of entry dicts (already shuffled)
        dataset_dir: path to dataset directory
        ordered: list of processor names in dependency order
        all_processors: dict {name: Processor}

    Returns:
        (sorted_todo, tier_counts) where tier_counts is Counter {tier: count}

    >>> priority_sort([], "datasets/pexels", ["a"], {})
    ([], Counter())
    """
    if not todo:
        return todo, Counter()

    # Compute tier for each entry
    tiers = []
    for entry in todo:
        sd = sample_dir(dataset_dir, entry["video_name"])
        tier = count_satisfied_deps(sd, ordered, all_processors)
        tiers.append(tier)

    # Stable sort descending by tier
    paired = list(zip(tiers, todo))
    paired.sort(key=lambda x: -x[0])

    sorted_todo = [entry for _, entry in paired]
    tier_counts = Counter(tiers)

    return sorted_todo, tier_counts


def format_processor_help(all_processors):
    """
    Format a help string listing all available processors with descriptions.
    Pure function.

    >>> class FakeProc:
    ...     def __init__(self, name, human, deps, fields):
    ...         self.name, self.human_name, self.depends_on, self.fields = name, human, deps, fields
    >>> procs = {"a": FakeProc("a", "Alpha Proc", [], {"x": {}}), "b": FakeProc("b", "Beta Proc", ["a"], {})}
    >>> 'a' in format_processor_help(procs) and 'Alpha Proc' in format_processor_help(procs)
    True
    """
    lines = ["Available processors:"]
    for name in sorted(all_processors.keys()):
        proc = all_processors[name]
        deps = f"depends_on={proc.depends_on}" if proc.depends_on else "no dependencies"
        field_names = list(proc.fields.keys())
        fields_str = f", fields: {field_names}" if field_names else ""
        lines.append(f"  {name:15s} {proc.human_name} ({deps}{fields_str})")
    return "\n".join(lines)


VALID_ARGS = {"dataset", "batch_size", "workers", "shuffle",
              "process", "skip", "auto_aggregate"}


def _validate_kwargs(kwargs, valid_args, script_name):
    """
    Reject unknown keyword arguments from Fire CLI. Exits on error.

    >>> _validate_kwargs({}, {"a", "b"}, "test.py")
    """
    if not kwargs:
        return
    unknown = sorted(set(kwargs.keys()) - valid_args)
    if unknown:
        print(f"ERROR: Unknown argument(s): {', '.join('--' + k for k in unknown)}")
        print(f"Valid arguments for {script_name}:")
        for arg in sorted(valid_args):
            print(f"  --{arg}")
        sys.exit(1)


def process_all(dataset=None, batch_size=500, workers=32, shuffle=True,
                process=None, skip=None, auto_aggregate=True, **kwargs):
    """
    Process videos in batches using the modular processor system.

    Processors are auto-discovered from preprocess/processors/.
    Dependencies are resolved automatically (e.g., --process=ingest auto-enables compress).

    After shuffle, videos are stable-sorted by prerequisite readiness: videos with more
    dependency artifacts already present get processed first. This maximizes throughput
    because ready-to-run processors don't have to wait for dependencies.

    Args:
        dataset: name of the dataset to process (e.g., "pexels", "web360"). REQUIRED.
        batch_size: videos per batch
        workers: CPU workers for parallel steps
        shuffle: randomize processing order for multi-machine safety (default True)
        process: comma-separated processor names to enable (+ their deps). REQUIRED.
        skip: comma-separated processor names to disable.
        auto_aggregate: run aggregator after each batch so server sees new data (default True, batch-scoped)
    """
    # 0. Validate CLI args
    _validate_kwargs(kwargs, VALID_ARGS, "process_all.py")

    # 1. Discover dataset and processor plugins
    from datasets import discover_datasets
    dataset_modules = discover_datasets(DATASETS_ROOT)

    all_processors = discover_processors()
    proc_names = sorted(all_processors.keys())

    # 1a. Require --dataset
    if dataset is None:
        print(f"\nERROR: --dataset is required. Specify which dataset to process.\n")
        print("Available datasets:")
        for name, ds_mod in sorted(dataset_modules.items()):
            print(f"  {name:20s} {ds_mod.human_name}")
        if not dataset_modules:
            print("  (none — create a dataset module in datasets/<name>/__init__.py)")
        sys.exit(1)

    if dataset not in dataset_modules:
        print(f"\nERROR: Unknown dataset '{dataset}'.\n")
        print("Available datasets:")
        for name, ds_mod in sorted(dataset_modules.items()):
            print(f"  {name:20s} {ds_mod.human_name}")
        sys.exit(1)

    dataset_dir = os.path.join(DATASETS_ROOT, dataset)
    manifest = os.path.join(dataset_dir, "manifest.json")

    # 1b. Require --process (no silent "run everything" default)
    if process is None and skip is None:
        print(f"\nERROR: --process is required. Specify which processors to run.\n")
        print(format_processor_help(all_processors))
        print(f"\nExamples:")
        print(f"  --process=ingest,phash          Run ingest + phash (+ their deps)")
        print(f"  --process=all                   Run all processors")
        print(f"  --process=all --skip=clip        Run all except clip")
        sys.exit(1)

    # 2. Determine enabled set
    if process is not None:
        if isinstance(process, str) and process.strip().lower() == "all":
            enabled = set(proc_names)
        else:
            enabled = set(_parse_name_list(process, proc_names, "--process"))
    else:
        enabled = set(proc_names)

    if skip is not None:
        to_skip = set(_parse_name_list(skip, proc_names, "--skip"))
        enabled -= to_skip

    # 3. Resolve dependencies (topological order)
    ordered = resolve_dependencies(enabled, all_processors)

    # 4. Print config
    print(f"\n{'='*60}")
    print(f"CONFIGURATION")
    print(f"{'='*60}")
    print(f"  dataset:        {dataset} ({dataset_modules[dataset].human_name})")
    print(f"  manifest:       {manifest}")
    print(f"  dataset_dir:    {dataset_dir}")
    print(f"  batch_size:     {batch_size}")
    print(f"  workers:        {workers}")
    print(f"  shuffle:        {shuffle}")
    print(f"  auto_aggregate: {auto_aggregate}")
    print(f"  processors:     {ordered}")
    for name in proc_names:
        status = "ENABLED" if name in ordered else "disabled"
        print(f"    {name}: {status}")
    print(f"{'='*60}\n")

    # 5. Load manifest
    _log(f"Loading manifest: {manifest}")
    with open(manifest) as f:
        entries = json.load(f)
    _log(f"Total videos: {len(entries)}")

    # 6. Find work: any enabled processor has missing artifacts
    todo = []
    for entry in entries:
        sd = sample_dir(dataset_dir, entry["video_name"])
        for pname in ordered:
            proc = all_processors[pname]
            if proc.needs_processing(sd):
                todo.append(entry)
                break

    _log(f"Videos needing work: {len(todo)}")

    if not todo:
        _log("Nothing to do!")
        return

    # 7. Shuffle for multi-machine safety
    if shuffle:
        random.shuffle(todo)
        _log("Shuffled processing order")

    # 8. Prerequisite priority sort (stable — preserves shuffle within tiers)
    todo, tier_counts = priority_sort(todo, dataset_dir, ordered, all_processors)
    _log(f"Prerequisite priority breakdown ({len(ordered)} processors):")
    print(format_tier_breakdown(tier_counts, len(ordered)))
    print()

    # 9. Batch loop
    total_start = time.time()
    num_batches = (len(todo) + batch_size - 1) // batch_size

    for batch_idx in range(num_batches):
        start = batch_idx * batch_size
        batch = todo[start:start + batch_size]
        batch_start = time.time()

        print(f"\n{'='*60}")
        _log(f"BATCH {batch_idx + 1}/{num_batches} — {len(batch)} videos")
        print(f"{'='*60}")

        for pname in ordered:
            proc = all_processors[pname]
            batch_todo = proc.filter_todo(batch, dataset_dir)

            if not batch_todo:
                _log(f"  {proc.human_name}: all {len(batch)} already done")
                continue

            t = time.time()
            _log(f"  {proc.human_name}: {len(batch_todo)}/{len(batch)} need processing...")
            proc.process(batch_todo, dataset_dir, workers)
            _log(f"  {proc.human_name} done in {time.time()-t:.0f}s")

        elapsed = time.time() - batch_start
        total_elapsed = time.time() - total_start
        remaining = (total_elapsed / (batch_idx + 1)) * (num_batches - batch_idx - 1)
        _log(f"Batch {batch_idx + 1} complete in {elapsed:.0f}s | Elapsed: {total_elapsed/60:.1f}min | ETA: {remaining/60:.1f}min")

        # 10. Auto-aggregate after each batch (batch-scoped, not full scan)
        if auto_aggregate:
            _log(f"Auto-aggregating {len(batch)} samples...")
            agg_start = time.time()
            from preprocess.aggregator import aggregate
            from preprocess.video_utils import sample_id as _sid
            dataset_name = os.path.basename(dataset_dir)
            batch_samples = [
                (_sid(dataset_name, e["video_name"]), sample_dir(dataset_dir, e["video_name"]))
                for e in batch
            ]
            aggregate(dataset_dir=dataset_dir, sample_list=batch_samples,
                      only_processors=ordered)
            _log(f"Aggregation done in {time.time()-agg_start:.0f}s")

    _log(f"ALL DONE in {(time.time()-total_start)/60:.1f}min")


if __name__ == "__main__":
    fire.Fire(process_all)
