"""
Tests for GVE processor plugin.
Run with: uv run python -m pytest tests/test_gve_processor.py -v
"""
import sys
import os
import json
import tempfile

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# --- GVE Processor class attribute tests ---

class TestGveProcessorAttributes:
    def test_import(self):
        from preprocess.processors.gve import GveProcessor
        assert GveProcessor.name == "gve"
        assert GveProcessor.human_name == "GVE Embeddings"

    def test_depends_on_ingest(self):
        from preprocess.processors.gve import GveProcessor
        assert GveProcessor.depends_on == ["ingest"]

    def test_artifacts_count(self):
        from preprocess.processors.gve import GveProcessor
        assert len(GveProcessor.artifacts) == 4

    def test_artifact_filenames(self):
        from preprocess.processors.gve import GveProcessor
        filenames = {a["filename"] for a in GveProcessor.artifacts}
        assert filenames == {"gve_embedding.npy", "gve_first.npy", "gve_last.npy", "gve_std.json"}

    def test_fields(self):
        from preprocess.processors.gve import GveProcessor
        assert "gve_std" in GveProcessor.fields
        assert GveProcessor.fields["gve_std"]["dtype"] == "float"

    def test_embedding_space(self):
        from preprocess.processors.gve import GveProcessor
        es = GveProcessor.embedding_space
        assert es["prefix"] == "gve"
        assert es["dim"] == 2048
        assert es["model"] == "Alibaba-NLP/GVE-3B"

    def test_score_field(self):
        from preprocess.processors.gve import GveProcessor
        sf = GveProcessor.embedding_space["score_field"]
        assert sf["key"] == "gve_score"
        assert sf["dynamic"] is True
        assert sf["range"] == [0, 1]
        assert sf["dtype"] == "float"

    def test_aggregation_rules(self):
        from preprocess.processors.gve import GveProcessor
        rules = GveProcessor.aggregation
        assert len(rules) == 2
        json_rule = [r for r in rules if r["type"] == "json_dict"][0]
        vec_rule = [r for r in rules if r["type"] == "vector_index"][0]
        assert json_rule["source"] == "gve_std.json"
        assert json_rule["target"] == "video_stats.json"
        assert vec_rule["prefix"] == "gve"
        assert vec_rule["dim"] == 2048


# --- No collision tests (GVE vs CLIP and SigLIP) ---

class TestNoCollisionWithOtherProcessors:
    def test_no_artifact_collision_clip(self):
        from preprocess.processors.gve import GveProcessor
        from preprocess.processors.clip import ClipProcessor
        gve_files = {a["filename"] for a in GveProcessor.artifacts}
        clip_files = {a["filename"] for a in ClipProcessor.artifacts}
        assert gve_files.isdisjoint(clip_files), f"Collision: {gve_files & clip_files}"

    def test_no_artifact_collision_siglip(self):
        from preprocess.processors.gve import GveProcessor
        from preprocess.processors.siglip import SiglipProcessor
        gve_files = {a["filename"] for a in GveProcessor.artifacts}
        siglip_files = {a["filename"] for a in SiglipProcessor.artifacts}
        assert gve_files.isdisjoint(siglip_files), f"Collision: {gve_files & siglip_files}"

    def test_no_field_collision(self):
        from preprocess.processors.gve import GveProcessor
        from preprocess.processors.clip import ClipProcessor
        from preprocess.processors.siglip import SiglipProcessor
        gve_fields = set(GveProcessor.fields.keys())
        clip_fields = set(ClipProcessor.fields.keys())
        siglip_fields = set(SiglipProcessor.fields.keys())
        assert gve_fields.isdisjoint(clip_fields), f"Collision: {gve_fields & clip_fields}"
        assert gve_fields.isdisjoint(siglip_fields), f"Collision: {gve_fields & siglip_fields}"

    def test_no_prefix_collision(self):
        from preprocess.processors.gve import GveProcessor
        from preprocess.processors.clip import ClipProcessor
        from preprocess.processors.siglip import SiglipProcessor
        prefixes = {
            GveProcessor.embedding_space["prefix"],
            ClipProcessor.embedding_space["prefix"],
            SiglipProcessor.embedding_space["prefix"],
        }
        assert len(prefixes) == 3, f"Prefix collision among: {prefixes}"

    def test_no_score_key_collision(self):
        from preprocess.processors.gve import GveProcessor
        from preprocess.processors.clip import ClipProcessor
        from preprocess.processors.siglip import SiglipProcessor
        keys = {
            GveProcessor.embedding_space["score_field"]["key"],
            ClipProcessor.embedding_space["score_field"]["key"],
            SiglipProcessor.embedding_space["score_field"]["key"],
        }
        assert len(keys) == 3, f"Score key collision among: {keys}"

    def test_discover_processors_validates(self):
        """Full discovery with collision validation passes for all three."""
        from preprocess.processors import discover_processors
        procs = discover_processors()
        assert "gve" in procs
        assert "clip" in procs
        assert "siglip" in procs


# --- needs_processing tests ---

class TestNeedsProcessing:
    def test_empty_dir_needs_processing(self):
        from preprocess.processors.gve import GveProcessor
        proc = GveProcessor()
        with tempfile.TemporaryDirectory() as td:
            assert proc.needs_processing(td) is True

    def test_complete_dir_does_not_need_processing(self):
        from preprocess.processors.gve import GveProcessor
        proc = GveProcessor()
        with tempfile.TemporaryDirectory() as td:
            for a in proc.artifacts:
                path = os.path.join(td, a["filename"])
                if path.endswith(".npy"):
                    np.save(path, np.zeros(2048, dtype=np.float16))
                else:
                    with open(path, "w") as f:
                        json.dump({}, f)
            assert proc.needs_processing(td) is False

    def test_partial_dir_needs_processing(self):
        from preprocess.processors.gve import GveProcessor
        proc = GveProcessor()
        with tempfile.TemporaryDirectory() as td:
            np.save(os.path.join(td, "gve_embedding.npy"), np.zeros(2048, dtype=np.float16))
            assert proc.needs_processing(td) is True


# --- batched forward doctest ---

class TestBatchedForward:
    def test_empty_images_returns_correct_shape(self):
        from preprocess.processors.gve import _batched_gve_forward
        result = _batched_gve_forward(None, None, [], "cpu", 4)
        assert result.shape == (0, 2048)
        assert result.dtype == np.float16


# --- encode_text tests (requires GPU + model download) ---

@pytest.mark.skipif(
    not os.environ.get("RUN_GPU_TESTS"),
    reason="Set RUN_GPU_TESTS=1 to run GPU-dependent tests"
)
class TestEncodeText:
    def test_encode_text_shape(self):
        from preprocess.processors.gve import GveProcessor
        result = GveProcessor.encode_text("a cat sitting on a mat")
        assert isinstance(result, np.ndarray)
        assert result.shape == (2048,)
        assert result.dtype == np.float32

    def test_encode_text_normalized(self):
        from preprocess.processors.gve import GveProcessor
        result = GveProcessor.encode_text("a beautiful sunset")
        norm = np.linalg.norm(result)
        assert abs(norm - 1.0) < 1e-5, f"Expected unit norm, got {norm}"

    def test_similar_queries_close(self):
        from preprocess.processors.gve import GveProcessor
        e1 = GveProcessor.encode_text("a cat")
        e2 = GveProcessor.encode_text("a kitten")
        e3 = GveProcessor.encode_text("a skyscraper in a city")
        sim_close = float(e1 @ e2)
        sim_far = float(e1 @ e3)
        assert sim_close > sim_far, f"'cat' vs 'kitten' ({sim_close:.3f}) should be more similar than 'cat' vs 'skyscraper' ({sim_far:.3f})"
