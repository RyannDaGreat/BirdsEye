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
    // Dynamic fields (e.g., score) are normalized into stats by the server
    for (const source of [item.metadata, item.stats]) {
      if (!source) continue;
      for (const [k, v] of Object.entries(source)) {
        if (typeof v === 'number') push(k, v);
      }
    }
  }
  return fields;
}

/** Common English stop words for caption word frequency analysis. */
const STOP_WORDS = new Set([
  'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
  'of', 'with', 'by', 'from', 'is', 'it', 'as', 'was', 'are', 'were',
  'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
  'will', 'would', 'could', 'should', 'may', 'might', 'shall', 'can',
  'not', 'no', 'nor', 'so', 'if', 'then', 'than', 'that', 'this',
  'these', 'those', 'which', 'who', 'whom', 'what', 'where', 'when',
  'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other',
  'some', 'such', 'only', 'own', 'same', 'too', 'very', 'just', 'about',
  'up', 'out', 'into', 'over', 'after', 'before', 'between', 'under',
  'through', 'during', 'while', 'its', 'their', 'his', 'her', 'my',
  'your', 'our', 'he', 'she', 'they', 'we', 'you', 'i', 'me', 'him',
  'us', 'them', 'also', 'there', 'here',
]);

/**
 * Extract content words from a caption string (lowercase, no stop words, length > 1).
 * Uses the same tokenization as wordFrequencies for consistent matching.
 * Pure function.
 *
 * @param {string} caption - raw caption text
 * @returns {Set<string>} set of lowercase content words
 *
 * >>> [...captionWords('A beautiful sunset over the ocean')].sort()
 * ['beautiful', 'ocean', 'sunset']
 */
export function captionWords(caption) {
  if (!caption) return new Set();
  const words = caption.toLowerCase()
    .split(/[\s,.;:!?'"()\[\]{}\-/\\]+/)
    .filter(w => w.length > 1 && !STOP_WORDS.has(w));
  return new Set(words);
}

/**
 * Compute word frequencies from caption text in result items.
 * Returns top N words sorted by frequency, excluding stop words.
 * Pure function.
 *
 * @param {object[]} items - result items with .caption property
 * @param {number} topN - maximum number of words to return
 * @returns {{word: string, count: number, pct: number}[]}
 */
export function wordFrequencies(items, topN = 30) {
  const counts = {};
  const videosWith = {};  // how many videos contain each word
  const nItems = items.length;
  for (const item of items) {
    const caption = (item.caption || '').toLowerCase();
    const words = caption.split(/[\s,.;:!?'"()\[\]{}\-/\\]+/).filter(w => w.length > 1 && !STOP_WORDS.has(w));
    const seen = new Set();
    for (const w of words) {
      counts[w] = (counts[w] || 0) + 1;
      if (!seen.has(w)) { videosWith[w] = (videosWith[w] || 0) + 1; seen.add(w); }
    }
  }
  if (nItems === 0) return [];
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, topN)
    .map(([word, count]) => ({ word, count, pct: (videosWith[word] || 0) / nItems }));
}

/**
 * Dequantize uint8 values (0-255) back to real values using known min/max.
 * Pure function.
 *
 * @param {number[]} quantized - array of 0-255 values
 * @param {number} min - original minimum
 * @param {number} max - original maximum
 * @returns {number[]}
 *
 * >>> dequantize([0, 128, 255], 0, 100)
 * [0, ~50.2, 100]
 */
export function dequantize(quantized, min, max) {
  const range = max - min;
  return quantized.map(q => min + (q / 255) * range);
}

/**
 * Compute Pearson correlation coefficient between two numeric arrays.
 * Returns r in [-1, 1]. Returns 0 if inputs are empty or constant.
 * Pure function.
 *
 * @param {number[]} xs
 * @param {number[]} ys
 * @returns {number}
 */
export function pearsonCorrelation(xs, ys) {
  const n = Math.min(xs.length, ys.length);
  if (n < 2) return 0;
  let sumX = 0, sumY = 0;
  for (let i = 0; i < n; i++) { sumX += xs[i]; sumY += ys[i]; }
  const meanX = sumX / n, meanY = sumY / n;
  let num = 0, denX = 0, denY = 0;
  for (let i = 0; i < n; i++) {
    const dx = xs[i] - meanX, dy = ys[i] - meanY;
    num += dx * dy;
    denX += dx * dx;
    denY += dy * dy;
  }
  const den = Math.sqrt(denX * denY);
  return den === 0 ? 0 : num / den;
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
