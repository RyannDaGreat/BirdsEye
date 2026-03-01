"""
Prepare a dataset for processing: hardlink videos, build manifest.json.

Usage:
    uv run python prepare_dataset.py <dataset_name>
    uv run python prepare_dataset.py web360
    uv run python prepare_dataset.py --all

For each dataset:
1. If the dataset module has a prepare() method, run it (e.g., hardlink videos)
2. Call build_manifest() to write/update manifest.json from entries()
"""

import os
import sys
import fire

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_ROOT)


def prepare(dataset_name=None, all=False):
    """Prepare one or all datasets."""
    from datasets import discover_datasets

    datasets_dir = os.path.join(REPO_ROOT, "datasets")
    modules = discover_datasets(datasets_dir)

    if not modules:
        print("No dataset modules found.")
        return

    if all:
        targets = list(modules.keys())
    elif dataset_name:
        if dataset_name not in modules:
            print(f"Unknown dataset '{dataset_name}'. Available: {list(modules.keys())}")
            return
        targets = [dataset_name]
    else:
        print("Usage: prepare_dataset.py <name> or --all")
        print(f"Available: {list(modules.keys())}")
        return

    for name in targets:
        ds = modules[name]
        ds_dir = os.path.join(datasets_dir, name)
        os.makedirs(ds_dir, exist_ok=True)

        print(f"\nPreparing {ds.human_name} ({name})...")

        # Run prepare() if the dataset has one (e.g., hardlink videos)
        if hasattr(ds, 'prepare') and callable(ds.prepare):
            ds.prepare()

        # Build manifest.json
        entries = ds.build_manifest(ds_dir)

        # Validate entries if it's a VideoDataset
        from datasets import VideoDataset
        if isinstance(ds, VideoDataset):
            ds.validate_entries(entries)

        print(f"  {name}: {len(entries)} entries ready")


if __name__ == "__main__":
    fire.Fire(prepare)
