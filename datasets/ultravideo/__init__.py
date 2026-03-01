"""
UltraVideo — high-quality video clips with rich aesthetic and technical annotations.

Source: UltraVideo research dataset (short clips subset).
49,604 clips with detailed captions, aesthetic scores, motion scores,
shot type, camera movement, lighting, and atmosphere descriptions.
"""

import csv
import os
import glob

from datasets import VideoDataset


# Path to external video clips (will be moved — only change this line)
ULTRAVIDEO_BASE = "/root/CleanCode/Dumps/UltraVideo/data"


class UltraVideoDataset(VideoDataset):
    name = "ultravideo"
    human_name = "UltraVideo"
    help_text = (
        "UltraVideo: 49,604 high-quality video clips (3-10s each) at up to 4K resolution. "
        "Each clip has: brief and detailed captions, aesthetic score, technical score, "
        "motion score, VTSS score, shot type, camera movement, lighting, and atmosphere. "
        "Source: UltraVideo research dataset (short clips subset)."
    )

    fields = {
        "vtss_score": {
            "label": "VTSS Score",
            "description": "Video-Text Semantic Similarity score. Higher = better caption-video alignment.",
            "dtype": "float",
        },
        "motion_score": {
            "label": "Motion Score",
            "description": "Camera and subject motion magnitude. Higher = more movement.",
            "dtype": "float",
        },
        "video_clip_score": {
            "label": "Video-CLIP Score",
            "description": "CLIP-based video quality/relevance score.",
            "dtype": "float",
        },
    }

    def _find_video(self, clip_id):
        """
        Find video file for a clip_id. Checks multiple resolution directories.
        Directory structure: clips_short_1920/clips_short_1920/UUID.mp4 (double nested).
        Returns path if found, None otherwise.
        """
        for subdir in ("clips_short_1920", "clips_short_960", "clips_short"):
            # Check double-nested (extracted from zip) and flat layouts
            for part_dir in sorted(glob.glob(os.path.join(ULTRAVIDEO_BASE, f"{subdir}*"))):
                if not os.path.isdir(part_dir):
                    continue
                # Double nested: clips_short_1920/clips_short_1920/UUID.mp4
                inner = os.path.join(part_dir, os.path.basename(part_dir))
                if os.path.isdir(inner):
                    path = os.path.join(inner, clip_id)
                    if os.path.exists(path):
                        return path
                # Flat: clips_short_1920_1/UUID.mp4
                path = os.path.join(part_dir, clip_id)
                if os.path.exists(path):
                    return path
        return None

    def _scan_available_clips(self):
        """
        Build {clip_filename: full_path} dict by scanning extracted directories.
        Fast: one readdir per directory instead of per-file stat.
        """
        available = {}
        for subdir in ("clips_short_1920", "clips_short_960", "clips_short"):
            for part_dir in sorted(glob.glob(os.path.join(ULTRAVIDEO_BASE, f"{subdir}*"))):
                if not os.path.isdir(part_dir):
                    continue
                # Check double-nested layout
                inner = os.path.join(part_dir, os.path.basename(part_dir))
                scan_dir = inner if os.path.isdir(inner) else part_dir
                for fname in os.listdir(scan_dir):
                    if fname.endswith(".mp4") and fname not in available:
                        available[fname] = os.path.join(scan_dir, fname)
        return available

    def entries(self):
        """
        Read entries from short.csv. Only includes clips whose video files exist.
        Uses 'Summarized Description' as caption for richness.
        """
        print("  Scanning available clips...")
        available = self._scan_available_clips()
        print(f"  Found {len(available)} clips on disk")

        csv_path = os.path.join(os.path.dirname(__file__), "short.csv")
        result = []
        skipped = 0

        with open(csv_path) as f:
            for row in csv.DictReader(f):
                clip_id = row["clip_id"]
                video_path = available.get(clip_id)
                if not video_path:
                    skipped += 1
                    continue

                entry = {
                    "video_name": clip_id.replace(".mp4", ""),
                    "caption": row.get("Summarized Description") or row.get("Brief Description", ""),
                    "source_path": os.path.abspath(video_path),
                }

                # Add numeric fields
                for field in self.fields:
                    val = row.get(field, "").strip()
                    if val:
                        entry[field] = float(val)

                result.append(entry)

        if skipped:
            print(f"  UltraVideo: {skipped} clips not found (still extracting?)")

        return result

    def prepare(self):
        """UltraVideo videos are read directly from the dump. No hardlinking needed."""
        entries = self.entries()
        print(f"  UltraVideo: {len(entries)} clips available")
