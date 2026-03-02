"""
Tests for pure functions across the codebase.
Run with: uv run python -m pytest tests/ -v
"""
import sys
import os
import json
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.search import (
    fuzzy_search,
    tokenize_query,
    match_entry,
    bin_values,
    sort_results,
    get_sort_value,
    paginate,
)


# --- search.py pure functions ---

class TestFuzzySearch:
    def test_empty_query_returns_all(self):
        entries = [{"video_name": "a", "caption": "cat"}, {"video_name": "b", "caption": "dog"}]
        assert len(fuzzy_search(entries, "", limit=100)) == 2

    def test_single_word_match(self):
        entries = [{"video_name": "1", "caption": "A cat on a mat"}, {"video_name": "2", "caption": "A dog in rain"}]
        result = fuzzy_search(entries, "cat")
        assert len(result) == 1
        assert result[0]["video_name"] == "1"

    def test_or_operator(self):
        entries = [{"video_name": "1", "caption": "cat"}, {"video_name": "2", "caption": "dog"}, {"video_name": "3", "caption": "bird"}]
        result = fuzzy_search(entries, "cat|dog", limit=100)
        assert len(result) == 2

    def test_negation(self):
        entries = [{"video_name": "1", "caption": "red car"}, {"video_name": "2", "caption": "blue car"}]
        result = fuzzy_search(entries, "car !red", limit=100)
        assert len(result) == 1
        assert result[0]["video_name"] == "2"

    def test_exact_phrase(self):
        entries = [{"video_name": "1", "caption": "blue sky mountains"}, {"video_name": "2", "caption": "blue mountains sky"}]
        result = fuzzy_search(entries, "'blue sky'", limit=100)
        assert len(result) == 1
        assert result[0]["video_name"] == "1"


class TestBinValues:
    def test_basic_binning(self):
        counts = bin_values([1, 2, 3, 4], 0, 4, 4)
        assert len(counts) == 4
        assert sum(counts) == 4

    def test_empty(self):
        assert bin_values([], 0, 10, 5) == [0, 0, 0, 0, 0]

    def test_single_value(self):
        counts = bin_values([5, 5, 5], 0, 10, 10)
        assert sum(counts) == 3


class TestSortResults:
    def test_sort_by_name_asc(self):
        items = [{"video_name": "b"}, {"video_name": "a"}, {"video_name": "c"}]
        result = sort_results(items, "name", "asc")
        assert [r["video_name"] for r in result] == ["a", "b", "c"]

    def test_sort_by_score_desc(self):
        items = [{"video_name": "a", "score": 0.3}, {"video_name": "b", "score": 0.9}]
        result = sort_results(items, "score", "desc")
        assert result[0]["video_name"] == "b"

    def test_empty_sort_key(self):
        items = [{"video_name": "a"}, {"video_name": "b"}]
        result = sort_results(items, "", "desc")
        assert len(result) == 2

    def test_random_sort_deterministic(self):
        items = [{"video_name": str(i)} for i in range(20)]
        r1 = sort_results(items, "random", random_seed=42)
        r2 = sort_results(items, "random", random_seed=42)
        assert [r["video_name"] for r in r1] == [r["video_name"] for r in r2]


class TestPaginate:
    def test_first_page(self):
        items = list(range(100))
        assert paginate(items, 1, 10) == list(range(10))

    def test_second_page(self):
        items = list(range(100))
        assert paginate(items, 2, 10) == list(range(10, 20))

    def test_beyond_end(self):
        items = list(range(5))
        assert paginate(items, 2, 10) == []


class TestGetSortValue:
    def test_score(self):
        assert get_sort_value({"video_name": "a", "score": 0.5}, "score") == 0.5

    def test_metadata(self):
        assert get_sort_value({"video_name": "a", "metadata": {"fps": 30}}, "fps") == 30

    def test_missing(self):
        assert get_sort_value({"video_name": "a"}, "nonexistent") is None
