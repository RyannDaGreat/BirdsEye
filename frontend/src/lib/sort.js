/**
 * Generic sorting for search results.
 * Looks up values from item.metadata and item.stats.
 * Dynamic fields (e.g., score) are in stats after server normalization.
 * All functions are pure.
 */
/** Resolve a sort key to a value from a result item. Pure function. */
export function getNestedValue(item, key) {
  if (!item) return undefined;
  if (key === 'name') return item.video_name;
  if (item.metadata && key in item.metadata) return item.metadata[key];
  if (item.stats && key in item.stats) return item.stats[key];
  return undefined;
}

// Sort options are now derived from availableFields() in lib/fields.js
// (single source of truth shared with FilterPanel)
