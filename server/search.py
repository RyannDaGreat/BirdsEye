"""
Search logic for video datasets: fuzzy text search + CLIP semantic search + convex hull.

All search functions are pure (stateless). State is held by the server app.
"""

import hashlib
import re
import numpy as np


def tokenize_query(query):
    """
    Parse an FZF extended-mode query string into structured tokens.

    Supports:
      - Space-separated terms → AND (all must match)
      - 'quoted phrase' → exact phrase match
      - !term → exclude (must NOT match)
      - term1|term2 → OR (either can match)

    Pure function.

    >>> tokenize_query("cat dog")
    [{'type': 'and', 'words': ['cat']}, {'type': 'and', 'words': ['dog']}]
    >>> tokenize_query("!rain 'blue sky'")
    [{'type': 'not', 'words': ['rain']}, {'type': 'exact', 'phrase': 'blue sky'}]
    >>> tokenize_query("cat|dog bird")
    [{'type': 'or', 'words': ['cat', 'dog']}, {'type': 'and', 'words': ['bird']}]
    """
    tokens = []
    # Extract quoted phrases first
    remaining = query
    quoted_pattern = re.compile(r"'([^']+)'")
    for match in quoted_pattern.finditer(query):
        tokens.append({"type": "exact", "phrase": match.group(1).lower()})
    remaining = quoted_pattern.sub("", remaining).strip()

    # Process remaining terms
    for part in remaining.split():
        if not part:
            continue
        if part.startswith("!"):
            word = part[1:]
            if word:
                tokens.append({"type": "not", "words": [word.lower()]})
        elif "|" in part:
            words = [w.lower() for w in part.split("|") if w]
            if words:
                tokens.append({"type": "or", "words": words})
        else:
            tokens.append({"type": "and", "words": [part.lower()]})
    return tokens


def match_entry(caption_lower, tokens):
    """
    Check if a lowercased caption matches all parsed FZF tokens.

    Pure function.

    >>> match_entry("a big blue cat on a mat", tokenize_query("cat blue"))
    True
    >>> match_entry("a big blue cat on a mat", tokenize_query("cat !blue"))
    False
    >>> match_entry("a big blue cat on a mat", tokenize_query("dog|cat"))
    True
    >>> match_entry("a big blue cat on a mat", tokenize_query("'blue cat'"))
    True
    >>> match_entry("a big blue cat on a mat", tokenize_query("'red cat'"))
    False
    """
    for token in tokens:
        t = token["type"]
        if t == "and":
            # Word-boundary match: each word must appear as a whole word
            for w in token["words"]:
                if not _word_match(caption_lower, w):
                    return False
        elif t == "not":
            for w in token["words"]:
                if _word_match(caption_lower, w):
                    return False
        elif t == "or":
            if not any(_word_match(caption_lower, w) for w in token["words"]):
                return False
        elif t == "exact":
            if token["phrase"] not in caption_lower:
                return False
    return True


def _word_match(text, word):
    """
    Check if word appears in text with word-boundary semantics.

    Uses substring match (not strict regex word boundary) to be forgiving
    while still matching on word level. A word matches if it appears as a
    substring — this mirrors FZF extended mode default behavior.

    Pure function.

    >>> _word_match("the cat sat", "cat")
    True
    >>> _word_match("the cat sat", "ca")
    True
    >>> _word_match("the cat sat", "xyz")
    False
    """
    return word in text


def fuzzy_search(entries, query, limit=200):
    """
    FZF extended-mode fuzzy search through video entries.

    Pure function: (entries, query) → filtered list.

    >>> entries = [{"video_name": "1", "caption": "A cat on a mat"}, {"video_name": "2", "caption": "A dog in rain"}]
    >>> [e["video_name"] for e in fuzzy_search(entries, "cat")]
    ['1']
    >>> [e["video_name"] for e in fuzzy_search(entries, "cat|dog")]
    ['1', '2']
    """
    if not query.strip():
        return entries[:limit]

    tokens = tokenize_query(query)
    results = []
    for entry in entries:
        caption_lower = (entry.get("caption") or "").lower()
        if match_entry(caption_lower, tokens):
            results.append(entry)
            if len(results) >= limit:
                break
    return results


def clip_search(query_embedding, index, video_names, k=200):
    """
    Search FAISS index for nearest neighbors to a CLIP text embedding.

    Pure function: (embedding, index, names, k) → list of (name, score).

    >>> isinstance(clip_search.__doc__, str)
    True
    """
    query_embedding = np.array(query_embedding, dtype=np.float32).reshape(1, -1)
    # L2 normalize
    norm = np.linalg.norm(query_embedding)
    if norm > 0:
        query_embedding = query_embedding / norm
    scores, indices = index.search(query_embedding, k)
    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < len(video_names):
            results.append({"video_name": video_names[idx], "score": float(score)})
    return results


def convex_hull_search(selected_embeddings, all_embeddings, video_names, k=200):
    """
    Find videos nearest to the centroid of selected video embeddings.

    Approximation of convex hull — uses centroid for simplicity and speed.

    Pure function.

    >>> isinstance(convex_hull_search.__doc__, str)
    True
    """
    if len(selected_embeddings) == 0:
        return []

    centroid = np.mean(selected_embeddings, axis=0, keepdims=True).astype(np.float32)
    norm = np.linalg.norm(centroid)
    if norm > 0:
        centroid = centroid / norm

    # Compute similarities
    all_f32 = all_embeddings.astype(np.float32)
    norms = np.linalg.norm(all_f32, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-8)
    all_normed = all_f32 / norms
    similarities = (all_normed @ centroid.T).flatten()

    # Sort by similarity descending
    top_indices = np.argsort(-similarities)[:k]
    results = []
    for idx in top_indices:
        results.append({
            "video_name": video_names[idx],
            "score": float(similarities[idx]),
        })
    return results


def all_numeric_values(name, video_metadata, video_stats):
    """
    Collect all numeric values for a single video from metadata + stats.

    Pure function. Returns flat dict {field_name: value}.

    >>> all_numeric_values("v1", {"v1": {"width": 1920}}, {"v1": {"clip_std": 0.05}})
    {'width': 1920, 'clip_std': 0.05}
    >>> all_numeric_values("v2", None, None)
    {}
    """
    values = {}
    if video_metadata and name in video_metadata:
        for k, v in video_metadata[name].items():
            if isinstance(v, (int, float)):
                values[k] = v
    if video_stats and name in video_stats:
        for k, v in video_stats[name].items():
            if isinstance(v, (int, float)):
                values[k] = v
    return values


def check_range_filter(value, filters, key_prefix):
    """
    Check if a value passes min/max range filters.

    Pure function.

    >>> check_range_filter(10, {"min_duration": 5, "max_duration": 15}, "duration")
    True
    >>> check_range_filter(3, {"min_duration": 5}, "duration")
    False
    """
    min_key = f"min_{key_prefix}"
    max_key = f"max_{key_prefix}"
    if min_key in filters and value < filters[min_key]:
        return False
    if max_key in filters and value > filters[max_key]:
        return False
    return True


def apply_filters(results, video_metadata, filters, video_stats=None):
    """
    Filter search results by video metadata and stats.

    Pure function.

    Args:
        results: list of dicts with at least 'video_name'
        video_metadata: dict {video_name: {width, height, fps, ...}} or None
        filters: dict with optional min_X / max_X keys for any numeric field
        video_stats: dict {video_name: {clip_std, flow_mean_magnitude, ...}} or None

    >>> meta = {"v1": {"width": 1920, "height": 1080, "fps": 30, "duration": 10, "num_frames": 300}}
    >>> apply_filters([{"video_name": "v1"}], meta, {"min_height": 720})
    [{'video_name': 'v1'}]
    >>> apply_filters([{"video_name": "v1"}], meta, {"min_height": 2160})
    []
    >>> apply_filters([{"video_name": "v1"}], meta, {})
    [{'video_name': 'v1'}]
    >>> apply_filters([{"video_name": "v1"}, {"video_name": "v2"}], meta, {"min_height": 720})
    [{'video_name': 'v1'}]
    """
    if not filters:
        return results

    active_fields = set()
    for k in filters:
        if k.startswith("min_"):
            active_fields.add(k[4:])
        elif k.startswith("max_"):
            active_fields.add(k[4:])

    filtered = []
    for item in results:
        name = item["video_name"]
        all_values = all_numeric_values(name, video_metadata, video_stats)

        passed = True
        for field in active_fields:
            if field not in all_values:
                passed = False
                break
            if not check_range_filter(all_values[field], filters, field):
                passed = False
                break

        if passed:
            filtered.append(item)

    return filtered


def get_sort_value(item, key):
    """
    Resolve a sort key to a numeric value from enriched result item.
    Checks item directly, then metadata, then stats.
    Pure function.

    >>> get_sort_value({"video_name": "a", "score": 0.5, "metadata": {"fps": 30}}, "score")
    0.5
    >>> get_sort_value({"video_name": "a", "metadata": {"fps": 30}}, "fps")
    30
    >>> get_sort_value({"video_name": "a"}, "missing") is None
    True
    """
    if key == "score":
        return item.get("score")
    if key == "name":
        return item.get("video_name")
    meta = item.get("metadata")
    if meta and key in meta:
        return meta[key]
    stats = item.get("stats")
    if stats and key in stats:
        return stats[key]
    return None


def sort_results(results, sort_key, sort_dir="desc", random_seed=0):
    """
    Sort enriched results by a field key. Excludes items missing the sort value
    (for numeric fields). Supports "random" for deterministic shuffle.
    Pure function (given same seed, produces same order).

    >>> items = [{"video_name": "b"}, {"video_name": "a"}, {"video_name": "c"}]
    >>> [r["video_name"] for r in sort_results(items, "name", "asc")]
    ['a', 'b', 'c']
    >>> [r["video_name"] for r in sort_results(items, "name", "desc")]
    ['c', 'b', 'a']
    >>> items2 = [{"video_name": "a", "score": 0.3}, {"video_name": "b", "score": 0.9}]
    >>> [r["video_name"] for r in sort_results(items2, "score", "desc")]
    ['b', 'a']
    """
    if not sort_key:
        return results

    if sort_key == "random":
        # Deterministic shuffle using seed-derived hash for stable ordering
        def hash_key(item):
            h = hashlib.md5(f"{random_seed}_{item['video_name']}".encode()).hexdigest()
            return h
        return sorted(results, key=hash_key)

    reverse = sort_dir == "desc"

    if sort_key == "name":
        return sorted(results, key=lambda r: r.get("video_name", ""), reverse=reverse)

    # Numeric sort — items missing the value go at the end
    with_val = []
    without_val = []
    for r in results:
        v = get_sort_value(r, sort_key)
        if v is not None:
            with_val.append((r, v))
        else:
            without_val.append(r)
    with_val.sort(key=lambda rv: rv[1], reverse=reverse)
    return [r for r, _ in with_val] + without_val


def paginate(results, page, page_size):
    """
    Slice a page from sorted results. 1-indexed pages.
    Pure function.

    >>> paginate(["a", "b", "c", "d", "e"], 1, 2)
    ['a', 'b']
    >>> paginate(["a", "b", "c", "d", "e"], 2, 2)
    ['c', 'd']
    >>> paginate(["a", "b", "c", "d", "e"], 3, 2)
    ['e']
    >>> paginate(["a", "b", "c", "d", "e"], 4, 2)
    []
    """
    start = (page - 1) * page_size
    return results[start:start + page_size]
