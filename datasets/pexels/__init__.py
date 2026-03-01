"""
Pexels video dataset. 81,766 videos with AI-generated captions.

Source: Pexels open-license video platform.
Manifest was pre-built by distill_metadata.py from the raw JSON dump.
"""

import json
import os

from datasets import VideoDataset


class PexelsDataset(VideoDataset):
    name = "pexels"
    human_name = "Pexels"
    fields = {}
    help_text = (
        "Pexels open-license video platform. 81,766 videos with AI-generated captions. "
        "Videos range from 1s to 12min, resolutions up to 4K. Diverse content: nature, "
        "cities, people, animals, aerial shots, abstract visuals."
    )

    def entries(self):
        """
        Read entries from the existing manifest.json.

        Pexels manifest was pre-built by distill_metadata.py.
        Each entry has: video_name, caption, source_path.
        """
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
        with open(manifest_path) as f:
            return json.load(f)
