/**
 * Generic sorting for search results.
 * Looks up values from item.metadata, item.stats, or item directly.
 * All functions are pure.
 */
import { parseSortKey } from './format.js';

/** Resolve a sort key to a value from a result item. Pure function. */
export function getNestedValue(item, key) {
  if (!item) return undefined;
  if (key === 'score') return item.score;
  if (key === 'name') return item.video_name;
  if (item.metadata && key in item.metadata) return item.metadata[key];
  if (item.stats && key in item.stats) return item.stats[key];
  return undefined;
}

/**
 * Seedable pseudo-random number generator (mulberry32).
 * Pure function: same seed always produces the same sequence.
 */
function mulberry32(seed) {
  return function() {
    seed |= 0; seed = seed + 0x6D2B79F5 | 0;
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

/**
 * Sort results by a sort key string like "score_desc" or "duration_asc".
 * Supports "random" as a special key — uses a seed for deterministic shuffle.
 * When sorting by a numeric field, excludes items that lack a value for that field.
 * Pure function (given the same seed, produces the same order).
 */
export function sortResults(results, sortKey, randomSeed = 0) {
  if (!sortKey) return results;
  const sorted = [...results];

  if (sortKey === 'random') {
    const rng = mulberry32(randomSeed);
    // Fisher-Yates shuffle with seeded RNG
    for (let i = sorted.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [sorted[i], sorted[j]] = [sorted[j], sorted[i]];
    }
    return sorted;
  }

  const { key, direction: dir } = parseSortKey(sortKey);
  const mult = dir === 'desc' ? -1 : 1;

  if (key === 'name') {
    sorted.sort((a, b) => mult * a.video_name.localeCompare(b.video_name));
  } else {
    // Exclude items without a value for the sort field
    const withValue = sorted.filter(item => getNestedValue(item, key) !== undefined);
    withValue.sort((a, b) => mult * (getNestedValue(a, key) - getNestedValue(b, key)));
    return withValue;
  }
  return sorted;
}

// Sort options are now derived from availableFields() in lib/fields.js
// (single source of truth shared with FilterPanel)
