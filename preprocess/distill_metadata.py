"""
Distill raw metadatas.json into a clean, uniform manifest.json for a dataset.

Pure function pipeline: raw JSON → deduplicated list of {video_name, caption, source_path}.

Usage:
    uv run python preprocess/distill_metadata.py --input metadatas.json --output datasets/pexels/manifest.json
"""

import json
import os
import fire


# Paths at top
DEFAULT_INPUT = "metadatas.json"
DEFAULT_OUTPUT = "datasets/pexels/manifest.json"


def extract_entries(raw_data):
    """
    Extract all video entries from the raw nested metadata structure.

    Pure function: dict-of-dicts-of-dicts → flat list of dicts.

    >>> data = {"ds1": {"k1": {"video_name": "1", "video_caption": ["cap", "src"], "cleancode_pexels_path": "/p/1.mp4"}}}
    >>> extract_entries(data)
    [{'video_name': '1', 'caption': 'cap', 'source_path': '/p/1.mp4'}]
    """
    entries = []
    for dataset_key, dataset_entries in raw_data.items():
        if not dataset_entries:
            continue
        for entry_key, entry in dataset_entries.items():
            video_name = entry.get("video_name")
            caption_list = entry.get("video_caption", [])
            source_path = entry.get("cleancode_pexels_path", "")
            if not video_name or not source_path:
                continue
            caption = caption_list[0] if isinstance(caption_list, list) and caption_list else ""
            entries.append({
                "video_name": str(video_name),
                "caption": caption,
                "source_path": source_path,
            })
    return entries


def deduplicate_entries(entries):
    """
    Deduplicate entries by video_name, keeping the first occurrence.

    Pure function.

    >>> deduplicate_entries([{"video_name": "1", "caption": "a"}, {"video_name": "1", "caption": "b"}, {"video_name": "2", "caption": "c"}])
    [{'video_name': '1', 'caption': 'a'}, {'video_name': '2', 'caption': 'c'}]
    """
    seen = set()
    result = []
    for entry in entries:
        name = entry["video_name"]
        if name not in seen:
            seen.add(name)
            result.append(entry)
    return result


def distill(input=DEFAULT_INPUT, output=DEFAULT_OUTPUT):
    """Distill raw metadata JSON into a clean manifest."""
    print(f"Loading {input}...")
    with open(input) as f:
        raw_data = json.load(f)

    print("Extracting entries...")
    entries = extract_entries(raw_data)
    print(f"  Extracted {len(entries)} entries")

    print("Deduplicating...")
    entries = deduplicate_entries(entries)
    print(f"  {len(entries)} unique entries")

    # Verify source paths exist
    missing = [e for e in entries if not os.path.exists(e["source_path"])]
    if missing:
        print(f"  WARNING: {len(missing)} entries have missing source videos")

    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w") as f:
        json.dump(entries, f)
    print(f"Wrote {output} ({len(entries)} entries, {os.path.getsize(output) / 1e6:.1f} MB)")


if __name__ == "__main__":
    fire.Fire(distill)
