"""
Tests for SigLIP processor plugin.
Run with: uv run python -m pytest tests/test_siglip_processor.py -v
"""
import sys
import os
import json
import tempfile
import shutil

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from preprocess.processors.base import mean_pairwise_cosine_distance


# --- Shared math function tests ---

class TestMeanPairwiseCosineDistance:
    def test_orthogonal_vectors(self):
        """Orthogonal unit vectors have max cosine distance = 1.0."""
        embs = np.eye(3, dtype=np.float32)
        assert mean_pairwise_cosine_distance(embs) == 1.0

    def test_identical_vectors(self):
        """Identical vectors have zero cosine distance."""
        embs = np.ones((3, 512), dtype=np.float32)
        assert mean_pairwise_cosine_distance(embs) == 0.0

    def test_two_vectors(self):
        """Two orthogonal vectors."""
        embs = np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32)
        assert mean_pairwise_cosine_distance(embs) == 1.0

    def test_1152_dim(self):
        """Works with SigLIP's 1152-dim embeddings."""
        embs = np.random.randn(4, 1152).astype(np.float32)
        result = mean_pairwise_cosine_distance(embs)
        assert 0.0 <= result <= 2.0  # cosine distance range


# --- SigLIP Processor class attribute tests ---

class TestSiglipProcessorAttributes:
    def test_import(self):
        from preprocess.processors.siglip import SiglipProcessor
        assert SiglipProcessor.name == "siglip"
        assert SiglipProcessor.human_name == "SigLIP Embeddings"

    def test_depends_on_ingest(self):
        from preprocess.processors.siglip import SiglipProcessor
        assert SiglipProcessor.depends_on == ["ingest"]

    def test_artifacts_count(self):
        from preprocess.processors.siglip import SiglipProcessor
        assert len(SiglipProcessor.artifacts) == 4

    def test_artifact_filenames(self):
        from preprocess.processors.siglip import SiglipProcessor
        filenames = {a["filename"] for a in SiglipProcessor.artifacts}
        assert filenames == {"siglip_embedding.npy", "siglip_first.npy", "siglip_last.npy", "siglip_std.json"}

    def test_fields(self):
        from preprocess.processors.siglip import SiglipProcessor
        assert "siglip_std" in SiglipProcessor.fields
        assert SiglipProcessor.fields["siglip_std"]["dtype"] == "float"

    def test_embedding_space(self):
        from preprocess.processors.siglip import SiglipProcessor
        es = SiglipProcessor.embedding_space
        assert es["prefix"] == "siglip"
        assert es["dim"] == 1152
        assert es["model"] == "google/siglip-so400m-patch14-384"

    def test_score_field(self):
        from preprocess.processors.siglip import SiglipProcessor
        sf = SiglipProcessor.embedding_space["score_field"]
        assert sf["key"] == "siglip_score"
        assert sf["dynamic"] is True
        assert sf["range"] == [0, 1]
        assert sf["dtype"] == "float"

    def test_aggregation_rules(self):
        from preprocess.processors.siglip import SiglipProcessor
        rules = SiglipProcessor.aggregation
        assert len(rules) == 2
        json_rule = [r for r in rules if r["type"] == "json_dict"][0]
        vec_rule = [r for r in rules if r["type"] == "vector_index"][0]
        assert json_rule["source"] == "siglip_std.json"
        assert json_rule["target"] == "video_stats.json"
        assert vec_rule["prefix"] == "siglip"
        assert vec_rule["dim"] == 1152


# --- No collision tests ---

class TestNoCollisionWithCLIP:
    def test_no_artifact_collision(self):
        from preprocess.processors.siglip import SiglipProcessor
        from preprocess.processors.clip import ClipProcessor
        siglip_files = {a["filename"] for a in SiglipProcessor.artifacts}
        clip_files = {a["filename"] for a in ClipProcessor.artifacts}
        assert siglip_files.isdisjoint(clip_files), f"Collision: {siglip_files & clip_files}"

    def test_no_field_collision(self):
        from preprocess.processors.siglip import SiglipProcessor
        from preprocess.processors.clip import ClipProcessor
        siglip_fields = set(SiglipProcessor.fields.keys())
        clip_fields = set(ClipProcessor.fields.keys())
        assert siglip_fields.isdisjoint(clip_fields), f"Collision: {siglip_fields & clip_fields}"

    def test_no_prefix_collision(self):
        from preprocess.processors.siglip import SiglipProcessor
        from preprocess.processors.clip import ClipProcessor
        siglip_prefix = SiglipProcessor.embedding_space["prefix"]
        clip_prefix = ClipProcessor.embedding_space["prefix"]
        assert siglip_prefix != clip_prefix

    def test_no_score_key_collision(self):
        from preprocess.processors.siglip import SiglipProcessor
        from preprocess.processors.clip import ClipProcessor
        siglip_key = SiglipProcessor.embedding_space["score_field"]["key"]
        clip_key = ClipProcessor.embedding_space["score_field"]["key"]
        assert siglip_key != clip_key

    def test_discover_processors_validates(self):
        """Full discovery with collision validation passes."""
        from preprocess.processors import discover_processors
        procs = discover_processors()
        assert "siglip" in procs
        assert "clip" in procs


# --- needs_processing tests ---

class TestNeedsProcessing:
    def test_empty_dir_needs_processing(self):
        from preprocess.processors.siglip import SiglipProcessor
        proc = SiglipProcessor()
        with tempfile.TemporaryDirectory() as td:
            assert proc.needs_processing(td) is True

    def test_complete_dir_does_not_need_processing(self):
        from preprocess.processors.siglip import SiglipProcessor
        proc = SiglipProcessor()
        with tempfile.TemporaryDirectory() as td:
            for a in proc.artifacts:
                path = os.path.join(td, a["filename"])
                if path.endswith(".npy"):
                    np.save(path, np.zeros(1152, dtype=np.float16))
                else:
                    with open(path, "w") as f:
                        json.dump({}, f)
            assert proc.needs_processing(td) is False

    def test_partial_dir_needs_processing(self):
        from preprocess.processors.siglip import SiglipProcessor
        proc = SiglipProcessor()
        with tempfile.TemporaryDirectory() as td:
            np.save(os.path.join(td, "siglip_embedding.npy"), np.zeros(1152, dtype=np.float16))
            assert proc.needs_processing(td) is True


# --- batched forward doctest ---

class TestBatchedForward:
    def test_empty_images_returns_correct_shape(self):
        from preprocess.processors.siglip import _batched_siglip_forward
        result = _batched_siglip_forward(None, None, [], "cpu", 32)
        assert result.shape == (0, 1152)
        assert result.dtype == np.float16


# --- encode_text tests (requires GPU/model download) ---

@pytest.mark.skipif(
    not os.environ.get("RUN_GPU_TESTS"),
    reason="Set RUN_GPU_TESTS=1 to run GPU-dependent tests"
)
class TestEncodeText:
    def test_encode_text_shape(self):
        from preprocess.processors.siglip import SiglipProcessor
        result = SiglipProcessor.encode_text("a cat sitting on a mat")
        assert isinstance(result, np.ndarray)
        assert result.shape == (1152,)
        assert result.dtype == np.float32

    def test_encode_text_normalized(self):
        from preprocess.processors.siglip import SiglipProcessor
        result = SiglipProcessor.encode_text("a beautiful sunset")
        norm = np.linalg.norm(result)
        assert abs(norm - 1.0) < 1e-5, f"Expected unit norm, got {norm}"

    def test_similar_queries_close(self):
        from preprocess.processors.siglip import SiglipProcessor
        e1 = SiglipProcessor.encode_text("a cat")
        e2 = SiglipProcessor.encode_text("a kitten")
        e3 = SiglipProcessor.encode_text("a skyscraper in a city")
        sim_close = float(e1 @ e2)
        sim_far = float(e1 @ e3)
        assert sim_close > sim_far, f"'cat' vs 'kitten' ({sim_close:.3f}) should be more similar than 'cat' vs 'skyscraper' ({sim_far:.3f})"
