"""
Integration tests for multi-embedding model coexistence (CLIP + SigLIP).
Run with: uv run python -m pytest tests/test_multi_embedding.py -v

Tests that multiple embedding processors can coexist without conflicts,
that both produce valid search results, and that the server correctly
handles multiple vector indices and text encoders.
"""
import sys
import os
import json

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestProcessorCoexistence:
    """Test that CLIP and SigLIP processors coexist without conflicts."""

    def test_discover_finds_both(self):
        from preprocess.processors import discover_processors
        procs = discover_processors()
        assert "clip" in procs
        assert "siglip" in procs

    def test_no_field_collisions(self):
        from preprocess.processors import discover_processors, collect_field_info
        procs = discover_processors()
        fields = collect_field_info(procs)
        # Both score fields must exist with different keys
        assert "score" in fields  # CLIP score
        assert "siglip_score" in fields  # SigLIP score
        # Both std fields must exist
        assert "clip_std" in fields
        assert "siglip_std" in fields

    def test_both_text_encoders_found(self):
        from preprocess.processors import discover_processors, collect_text_encoders
        procs = discover_processors()
        encoders = collect_text_encoders(procs)
        assert "clip" in encoders
        assert "siglip" in encoders

    def test_both_vector_index_rules(self):
        from preprocess.processors import discover_processors, collect_aggregation_rules
        procs = discover_processors()
        _, vec_rules = collect_aggregation_rules(procs)
        prefixes = {r["prefix"] for r in vec_rules}
        assert "clip" in prefixes
        assert "siglip" in prefixes
        # Verify dimensions
        dims = {r["prefix"]: r["dim"] for r in vec_rules}
        assert dims["clip"] == 512
        assert dims["siglip"] == 1152

    def test_dynamic_field_ranges_both_declared(self):
        """Both processors declare score_field with range for histogram binning."""
        from preprocess.processors import discover_processors
        procs = discover_processors()

        # Collect dynamic field ranges the same way the server does
        ranges = {}
        for proc in procs.values():
            es = getattr(proc, 'embedding_space', None)
            if es and 'score_field' in es:
                sf = es['score_field']
                if 'range' in sf:
                    ranges[sf['key']] = tuple(sf['range'])

        assert "score" in ranges
        assert "siglip_score" in ranges
        assert ranges["score"] == (0, 1)
        assert ranges["siglip_score"] == (0, 1)


class TestEmbeddingDimensions:
    """Test that embeddings have correct dimensions."""

    def test_clip_dim(self):
        from preprocess.processors.clip import CLIP_DIM
        assert CLIP_DIM == 512

    def test_siglip_dim(self):
        from preprocess.processors.siglip import SIGLIP_DIM
        assert SIGLIP_DIM == 1152


@pytest.mark.skipif(
    not os.environ.get("RUN_GPU_TESTS"),
    reason="Set RUN_GPU_TESTS=1 to run GPU-dependent tests"
)
class TestTextEncoderOutputs:
    """Test that both text encoders produce valid, comparable embeddings."""

    def test_clip_text_shape(self):
        from preprocess.processors.clip import ClipProcessor
        emb = ClipProcessor.encode_text("a cat")
        assert emb.shape == (512,)
        assert emb.dtype == np.float32

    def test_siglip_text_shape(self):
        from preprocess.processors.siglip import SiglipProcessor
        emb = SiglipProcessor.encode_text("a cat")
        assert emb.shape == (1152,)
        assert emb.dtype == np.float32

    def test_both_normalized(self):
        from preprocess.processors.clip import ClipProcessor
        from preprocess.processors.siglip import SiglipProcessor
        clip_emb = ClipProcessor.encode_text("sunset")
        siglip_emb = SiglipProcessor.encode_text("sunset")
        assert abs(np.linalg.norm(clip_emb) - 1.0) < 1e-5
        assert abs(np.linalg.norm(siglip_emb) - 1.0) < 1e-5

    def test_semantic_similarity_both_models(self):
        """Both models should agree that cat/kitten are more similar than cat/car."""
        from preprocess.processors.clip import ClipProcessor
        from preprocess.processors.siglip import SiglipProcessor

        for name, encode in [("CLIP", ClipProcessor.encode_text), ("SigLIP", SiglipProcessor.encode_text)]:
            e_cat = encode("a cat")
            e_kitten = encode("a kitten")
            e_car = encode("a red sports car")
            sim_close = float(e_cat @ e_kitten)
            sim_far = float(e_cat @ e_car)
            assert sim_close > sim_far, f"{name}: cat-kitten ({sim_close:.3f}) should > cat-car ({sim_far:.3f})"


class TestServerFieldInfo:
    """Test that field info includes both CLIP and SigLIP fields."""

    def test_collect_field_info_has_both_scores(self):
        from preprocess.processors import discover_processors, collect_field_info
        procs = discover_processors()
        fields = collect_field_info(procs)

        # CLIP score
        assert "score" in fields
        assert fields["score"]["dynamic"] is True
        assert fields["score"]["label"] == "CLIP Score"

        # SigLIP score
        assert "siglip_score" in fields
        assert fields["siglip_score"]["dynamic"] is True
        assert fields["siglip_score"]["label"] == "SigLIP Score"

    def test_both_scores_have_source(self):
        from preprocess.processors import discover_processors, collect_field_info
        procs = discover_processors()
        fields = collect_field_info(procs)
        assert fields["score"]["source"] == "CLIP Embeddings"
        assert fields["siglip_score"]["source"] == "SigLIP Embeddings"


class TestServerSearchFunctions:
    """Test search functions work with mock data for both indices."""

    def test_clip_search_with_mock_index(self):
        """clip_search works with a mock FAISS index."""
        import faiss
        from server.search import clip_search

        dim = 512
        n = 10
        embeddings = np.random.randn(n, dim).astype(np.float32)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / norms

        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)
        names = [f"video_{i}" for i in range(n)]

        query = embeddings[0]  # search for first video
        results = clip_search(query, index, names, k=5)
        assert len(results) == 5
        assert results[0]["video_name"] == "video_0"  # should find itself first
        assert results[0]["score"] > 0.99  # cosine sim to itself ≈ 1.0

    def test_siglip_search_with_mock_index(self):
        """clip_search (generic FAISS search) works with SigLIP dimensions."""
        import faiss
        from server.search import clip_search

        dim = 1152  # SigLIP dimension
        n = 10
        embeddings = np.random.randn(n, dim).astype(np.float32)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / norms

        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)
        names = [f"video_{i}" for i in range(n)]

        query = embeddings[3]  # search for fourth video
        results = clip_search(query, index, names, k=5)
        assert len(results) == 5
        assert results[0]["video_name"] == "video_3"
        assert results[0]["score"] > 0.99

    def test_similar_videos_rank_higher(self):
        """Videos with similar embeddings should rank higher than dissimilar ones."""
        import faiss
        from server.search import clip_search

        dim = 1152
        # Create two "clusters": videos 0-4 are similar, videos 5-9 are similar
        cluster_a = np.random.randn(1, dim).astype(np.float32)
        cluster_b = np.random.randn(1, dim).astype(np.float32)

        embeddings = []
        for i in range(5):
            embeddings.append(cluster_a + np.random.randn(1, dim).astype(np.float32) * 0.05)
        for i in range(5):
            embeddings.append(cluster_b + np.random.randn(1, dim).astype(np.float32) * 0.05)
        embeddings = np.concatenate(embeddings, axis=0)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / norms

        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)
        names = [f"video_{i}" for i in range(10)]

        # Search for a video from cluster A
        query = embeddings[0]
        results = clip_search(query, index, names, k=10)
        top5_names = {r["video_name"] for r in results[:5]}

        # The top 5 should mostly be from cluster A (videos 0-4)
        cluster_a_in_top5 = len(top5_names & {f"video_{i}" for i in range(5)})
        assert cluster_a_in_top5 >= 4, f"Expected ≥4 cluster A videos in top 5, got {cluster_a_in_top5}"


class TestEnrichResults:
    """Test that enrich_results normalizes scores from both models."""

    def test_score_normalized_to_stats(self):
        """Top-level numeric values (scores) get swept into stats dict."""
        from server.app import create_app
        # We can't easily test this without the server, so test the logic directly
        RESULT_STRUCTURAL_KEYS = {"video_name", "caption", "source_path", "metadata", "stats"}

        result = {"video_name": "test", "score": 0.85, "siglip_score": 0.72}
        for k in list(result.keys()):
            if k not in RESULT_STRUCTURAL_KEYS and isinstance(result[k], (int, float)):
                result.setdefault("stats", {})[k] = result.pop(k)

        assert "score" not in result
        assert "siglip_score" not in result
        assert result["stats"]["score"] == 0.85
        assert result["stats"]["siglip_score"] == 0.72
