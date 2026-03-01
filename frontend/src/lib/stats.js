/**
 * Aggregate statistics computation for result sets.
 * All functions are pure.
 */

/**
 * Extract all numeric fields from enriched result items.
 * Returns { fieldName: [values] } for every numeric field found.
 * Pure function.
 */
export function collectNumericFields(items) {
  const fields = {};
  const push = (k, v) => { (fields[k] = fields[k] || []).push(v); };

  for (const item of items) {
    if (item.score !== undefined) push('score', item.score);
    // Iterate metadata + stats — no hardcoded field names
    for (const source of [item.metadata, item.stats]) {
      if (!source) continue;
      for (const [k, v] of Object.entries(source)) {
        if (typeof v === 'number') push(k, v);
      }
    }
  }
  return fields;
}

/**
 * Summarize an array of numbers: {mean, min, max, std}.
 * Pure function.
 */
export function summarize(values) {
  if (!values.length) return { mean: 0, min: 0, max: 0, std: 0 };
  const n = values.length;
  const mean = values.reduce((a, b) => a + b, 0) / n;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const variance = values.reduce((acc, v) => acc + (v - mean) ** 2, 0) / n;
  return { mean, min, max, std: Math.sqrt(variance) };
}
