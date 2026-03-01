"""
Web360 panoramic video dataset. 2,114 360-degree videos with AI-generated captions.

Source: WEB360_360TF_train.csv from the Web360 research dataset.
Videos are 512x1024 resolution, 100 frames each.
"""

import csv
import os

from datasets import VideoDataset


# Path to the external video source (hardlinks made at prepare time)
WEB360_SOURCE = "/root/CleanCode/Dumps/Web360/datasets/web360/videos_512x1024x100"


class Web360Dataset(VideoDataset):
    name = "web360"
    human_name = "Web360"
    fields = {}
    help_text = (
        "Web360 panoramic video dataset. 2,114 360-degree videos (512x1024) at 20fps. "
        "AI-generated captions describe scenes from an omnidirectional perspective. "
        "Source: WEB360_360TF_train split from the Web360 research dataset."
    )

    def entries(self):
        """
        Read entries from the CSV. Video source_path points to local hardlinks
        (created by prepare()).

        Each entry has: video_name, caption, source_path.
        """
        csv_path = os.path.join(os.path.dirname(__file__), "WEB360_360TF_train.csv")
        videos_dir = os.path.join(os.path.dirname(__file__), "videos")

        result = []
        with open(csv_path) as f:
            for row in csv.DictReader(f):
                video_name = row["videoid"]
                video_file = os.path.join(videos_dir, f"{video_name}.mp4")
                if os.path.exists(video_file):
                    result.append({
                        "video_name": video_name,
                        "caption": row["name"],
                        "source_path": os.path.abspath(video_file),
                    })

        return result

    def prepare(self):
        """
        Hardlink videos from the external Web360 dump into this dataset's
        local videos/ directory. Makes the dataset self-contained.

        Idempotent: skips already-linked files.
        """
        videos_dir = os.path.join(os.path.dirname(__file__), "videos")
        os.makedirs(videos_dir, exist_ok=True)

        csv_path = os.path.join(os.path.dirname(__file__), "WEB360_360TF_train.csv")
        with open(csv_path) as f:
            rows = list(csv.DictReader(f))

        linked = skipped = missing = 0
        for row in rows:
            video_name = row["videoid"]
            src = os.path.join(WEB360_SOURCE, f"{video_name}.mp4")
            dst = os.path.join(videos_dir, f"{video_name}.mp4")

            if os.path.exists(dst):
                skipped += 1
                continue
            if not os.path.exists(src):
                missing += 1
                continue

            try:
                os.link(src, dst)
                linked += 1
            except OSError:
                os.symlink(os.path.abspath(src), dst)
                linked += 1

        print(f"  Web360 prepare: {linked} linked, {skipped} skipped, {missing} missing")
