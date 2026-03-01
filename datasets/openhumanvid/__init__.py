"""
OpenHumanVid — high-quality human-centric video dataset with rich annotations.

Source: HQ-OpenHumanVid research dataset.
Each clip has: video, caption, luminance stats, blur stats, aesthetic score,
technical score, and global motion metrics.
"""

import csv
import os
import glob

from datasets import VideoDataset


# Base path for extracted video parts
OPENHUMANVID_BASE = "/root/CleanCode/Dumps/OpenHumanVid/HQ-OpenHumanVid"


class OpenHumanVidDataset(VideoDataset):
    name = "openhumanvid"
    human_name = "OpenHumanVid"
    help_text = (
        "HQ-OpenHumanVid: high-quality human-centric video clips with rich annotations. "
        "Each clip has luminance, blur, aesthetic, technical, and motion scores. "
        "Captions describe human activities, poses, and scenes in detail."
    )

    fields = {
        "luminance_min": {
            "label": "Luminance Min",
            "description": "Minimum luminance value across video frames (0-255 scale).",
            "dtype": "float",
        },
        "luminance_max": {
            "label": "Luminance Max",
            "description": "Maximum luminance value across video frames (0-255 scale).",
            "dtype": "float",
        },
        "blur_min": {
            "label": "Blur Min",
            "description": "Minimum blur score across frames. Lower = sharper.",
            "dtype": "float",
        },
        "blur_max": {
            "label": "Blur Max",
            "description": "Maximum blur score across frames. Higher = blurrier.",
            "dtype": "float",
        },
        "aesthetic": {
            "label": "Aesthetic Score",
            "description": "AI-predicted aesthetic quality score. Higher = more visually pleasing.",
            "dtype": "float",
        },
        "technical_score": {
            "label": "Technical Score",
            "description": "Technical quality score (compression artifacts, noise, etc.). Higher = better quality.",
            "dtype": "float",
        },
        "global_motion": {
            "label": "Global Motion",
            "description": "Global camera motion magnitude. Higher = more camera movement.",
            "dtype": "float",
        },
    }

    aggregation = []  # Fields are dataset-native, not from processors

    def _csv_paths(self):
        """Find all CSV files in this dataset directory."""
        ds_dir = os.path.dirname(__file__)
        return sorted(glob.glob(os.path.join(ds_dir, "OpenHumanVid_part_*.csv")))

    def _video_path(self, csv_path_field):
        """
        Convert CSV path field to actual video file path.
        CSV: 'clips/part_001/f6/05/f605b8e91db3dd66865f3ea1b4e3621d'
        File: '<base>/part_001/f6/05/f605b8e91db3dd66865f3ea1b4e3621d.mp4'
        """
        local = csv_path_field.replace("clips/", "") + ".mp4"
        return os.path.join(OPENHUMANVID_BASE, local)

    def _find_extracted_parts(self):
        """Find which part directories are extracted (fast: just ls top-level)."""
        parts = []
        for name in sorted(os.listdir(OPENHUMANVID_BASE)):
            if name.startswith("part_") and os.path.isdir(os.path.join(OPENHUMANVID_BASE, name)):
                parts.append(name)
        return parts

    def entries(self):
        """
        Read entries from CSVs for extracted parts only. Assumes all videos in
        extracted parts exist (avoids per-file stat on NFS which is prohibitively slow).
        Each entry has: video_name, caption, source_path, plus all 7 numeric fields.
        """
        extracted = set(self._find_extracted_parts())
        print(f"  Extracted parts: {sorted(extracted)}")

        result = []
        for csv_path in self._csv_paths():
            # Only include entries whose part is extracted
            part_name = os.path.basename(csv_path).replace("OpenHumanVid_", "").replace(".csv", "")
            if part_name not in extracted:
                continue

            with open(csv_path) as f:
                for row in csv.DictReader(f):
                    video_file = self._video_path(row["path"])
                    entry = {
                        "video_name": row["clip_id"],
                        "caption": row["caption"],
                        "source_path": os.path.abspath(video_file),
                    }

                    # Add numeric fields
                    for field in self.fields:
                        val = row.get(field, "").strip()
                        if val:
                            entry[field] = float(val)

                    result.append(entry)

        return result

    def prepare(self):
        """
        OpenHumanVid videos are read directly from the extracted dump location.
        No hardlinking needed — the videos are in the external dump at known paths.
        If you need self-containment, implement hardlinking here.
        """
        # Count available videos
        total = 0
        missing = 0
        for csv_path in self._csv_paths():
            with open(csv_path) as f:
                for row in csv.DictReader(f):
                    video_file = self._video_path(row["path"])
                    if os.path.exists(video_file):
                        total += 1
                    else:
                        missing += 1
        print(f"  OpenHumanVid: {total} videos available, {missing} missing")
