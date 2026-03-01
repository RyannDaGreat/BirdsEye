"""
Dataset plugin system. Each dataset is a Python package under datasets/.

Auto-discovers dataset modules: adding a new dataset = dropping a folder with
__init__.py containing a Dataset subclass. No registration needed.

Validates on load:
- No duplicate dataset names
- No field name collisions between datasets and processors
- No artifact name collisions between datasets and processors
"""

import os
import importlib
from abc import ABC, abstractmethod


class Dataset(ABC):
    """
    Base class for all dataset plugins.

    Subclasses MUST define:
        name: str        — machine name, e.g., "pexels". Must match folder name.
        human_name: str  — display name, e.g., "Pexels"

    Subclasses MAY define:
        fields: dict     — {field_name: {label, description, dtype}}. Extra fields
                           this dataset provides per entry (beyond video_name/caption).
                           These show up in sort/filter/histogram in the UI.

    Subclasses MUST implement:
        entries() -> list[dict]  — return all entries for this dataset.
    """

    name: str
    human_name: str
    fields: dict = {}

    def __init_subclass__(cls, **kwargs):
        """Validate that subclasses define required class attributes."""
        super().__init_subclass__(**kwargs)
        # Skip intermediate base classes that don't define 'name' in their own dict
        if 'name' not in cls.__dict__:
            return
        for attr in ("name", "human_name"):
            if not getattr(cls, attr, None):
                raise TypeError(
                    f"Dataset subclass {cls.__name__} must define class attribute '{attr}'"
                )

    @abstractmethod
    def entries(self):
        """
        Return all entries for this dataset as a list of dicts.

        Each dict MUST have at minimum 'video_name'.
        VideoDataset subclasses also require 'caption' and 'source_path'.
        """

    def build_manifest(self, dataset_dir):
        """
        Write manifest.json from entries(). The manifest is the interface
        between the dataset module and the processing pipeline.

        Returns the entry list.
        """
        import json
        from preprocess.video_utils import save_json_atomic

        all_entries = self.entries()
        manifest_path = os.path.join(dataset_dir, "manifest.json")
        save_json_atomic(all_entries, manifest_path)
        print(f"  Wrote manifest.json: {len(all_entries)} entries")
        return all_entries


class VideoDataset(Dataset):
    """
    Base class for video-based datasets. Entries must have:
      - video_name: str  — unique identifier for the video
      - caption: str     — text description
      - source_path: str — path to the video file on disk
    """

    def validate_entries(self, entries):
        """
        Check that all entries have required video fields.
        Raises ValueError on first invalid entry.

        >>> class D(VideoDataset):
        ...     name = "test"; human_name = "Test"
        ...     def entries(self): return []
        >>> D().validate_entries([{"video_name": "1", "caption": "hi", "source_path": "/x"}])
        """
        for i, e in enumerate(entries):
            for req in ("video_name", "caption", "source_path"):
                if req not in e:
                    raise ValueError(
                        f"Entry {i} missing required field '{req}': {e}"
                    )


def discover_datasets(datasets_dir):
    """
    Scan datasets/ directory for Python packages with Dataset subclasses.
    Returns {name: dataset_instance}.

    Falls back gracefully: directories without __init__.py are skipped
    (they can still be loaded via manifest.json by the server).

    Reads filesystem.

    >>> discover_datasets("/nonexistent_xyz_dir")
    {}
    """
    found = {}
    if not os.path.isdir(datasets_dir):
        return found

    for name in sorted(os.listdir(datasets_dir)):
        ds_path = os.path.join(datasets_dir, name)
        init_path = os.path.join(ds_path, "__init__.py")
        if not os.path.isdir(ds_path) or not os.path.exists(init_path):
            continue

        mod = importlib.import_module(f"datasets.{name}")
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if (isinstance(attr, type) and issubclass(attr, Dataset)
                    and attr is not Dataset and attr is not VideoDataset
                    and hasattr(attr, 'name') and attr.name):
                instance = attr()
                found[instance.name] = instance

    if found:
        names = sorted(found.keys())
        print(f"Discovered {len(names)} dataset module(s): {', '.join(names)}")
        for n in names:
            ds = found[n]
            n_fields = len(ds.fields)
            print(f"  {n}: {ds.human_name} | {n_fields} fields")

    return found


def validate_no_collisions(datasets, processors):
    """
    Check that no dataset field or artifact name collides with processor names.
    Raises ValueError on conflict.

    Pure function.

    >>> validate_no_collisions({}, {})
    """
    # Collect all processor field names
    proc_fields = set()
    for proc in processors.values():
        proc_fields.update(proc.fields.keys())

    # Collect all processor artifact filenames
    proc_artifacts = set()
    for proc in processors.values():
        for a in proc.artifacts:
            proc_artifacts.add(a["filename"])

    # Check dataset fields against processor fields
    for ds_name, ds in datasets.items():
        for field_name in ds.fields:
            if field_name in proc_fields:
                raise ValueError(
                    f"Field name collision: '{field_name}' is defined by both "
                    f"dataset '{ds_name}' and a processor"
                )

    # Check dataset fields don't collide with each other
    seen_fields = {}
    for ds_name, ds in datasets.items():
        for field_name in ds.fields:
            if field_name in seen_fields:
                raise ValueError(
                    f"Field name collision: '{field_name}' is defined by both "
                    f"dataset '{ds_name}' and dataset '{seen_fields[field_name]}'"
                )
            seen_fields[field_name] = ds_name
