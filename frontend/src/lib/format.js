/**
 * Shared formatting functions. All pure.
 */
import { sortFieldKeys } from './fields.js';

/**
 * Format a number for display: integers stay whole, floats get fixed decimals.
 * Pure function.
 */
export function formatNumber(val, decimals = 2) {
  if (val === undefined || val === null || val === '') return '';
  const n = Number(val);
  if (isNaN(n)) return String(val);
  return Number.isInteger(n) ? String(n) : n.toFixed(decimals);
}

/**
 * Parse a sort key string like "duration_desc" into {key, direction}.
 * Pure function.
 */
export function parseSortKey(sortStr) {
  if (!sortStr) return { key: '', direction: '' };
  if (sortStr === 'random') return { key: 'random', direction: 'desc' };
  const i = sortStr.lastIndexOf('_');
  if (i === -1) return { key: sortStr, direction: 'desc' };
  return { key: sortStr.substring(0, i), direction: sortStr.substring(i + 1) };
}

/**
 * Compute CSS background-position for a sprite grid cell.
 * Pure function.
 */
export function spritePosition(frameIndex, cols = 5, rows = 5) {
  const col = frameIndex % cols;
  const row = Math.floor(frameIndex / cols);
  const colPct = cols > 1 ? col * 100 / (cols - 1) : 0;
  const rowPct = rows > 1 ? row * 100 / (rows - 1) : 0;
  return `${colPct}% ${rowPct}%`;
}

/**
 * Clamp a frame index from mouse position.
 * Pure function.
 */
export function mouseToFrameIndex(mouseXFraction, totalFrames = 25) {
  return Math.min(totalFrames - 1, Math.max(0, Math.floor(mouseXFraction * totalFrames)));
}

/**
 * Truncate text to a max length.
 * Pure function.
 */
export function truncate(text, maxLen = 120) {
  if (!text) return '';
  return text.length > maxLen ? text.substring(0, maxLen) + '...' : text;
}

/**
 * Escape HTML entities for safe display.
 * Pure function (uses DOM but is deterministic).
 */
export function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text || '';
  return div.innerHTML;
}

/**
 * Highlight search terms in text by wrapping matches in <b><u>...</u></b>.
 * Escapes HTML first to prevent injection, then applies highlights.
 * Handles FZF extended syntax: space = AND, 'quoted' = exact, |=OR, !term excluded.
 * Pure function.
 */
export function highlightTerms(text, query) {
  if (!text || !query || !query.trim()) return escapeHtml(text);

  const escaped = escapeHtml(text);

  // Extract search terms from FZF query (skip ! negations and 'quoted' phrases handled separately)
  const terms = [];
  const remaining = query.replace(/'([^']+)'/g, (_, phrase) => {
    terms.push(phrase);
    return '';
  });
  for (const part of remaining.split(/\s+/)) {
    if (!part || part.startsWith('!')) continue;
    for (const t of part.split('|')) {
      if (t) terms.push(t);
    }
  }

  if (!terms.length) return escaped;

  // Build regex from all terms (case-insensitive)
  const pattern = terms.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
  const regex = new RegExp(`(${pattern})`, 'gi');

  return escaped.replace(regex, '<b><u>$1</u></b>');
}

/**
 * Prepend a marker to a dynamic field name for display in sort dropdowns.
 * Dynamic fields are computed on-the-fly (not stored on disk).
 * The marker is defined here so it can be changed project-wide in one place.
 * Pure function.
 *
 * Examples:
 *   dynamicFieldLabel('CLIP Score')  → '✦ CLIP Score'
 *   dynamicFieldLabel('Video Score') → '✦ Video Score'
 */
export function dynamicFieldLabel(name) {
  return `✦ ${name}`;
}

/**
 * Compute fixed-position tooltip coordinates from a mouse event.
 * Returns {x, y} in viewport pixels, offset so the tooltip appears
 * to the right and slightly above the cursor.
 * Pure function.
 *
 * @param {MouseEvent} e
 * @returns {{x: number, y: number}}
 *
 * >>> // tipPos({clientX: 100, clientY: 200}) → {x: 112, y: 192}
 */
const TIP_OFFSET_X = 12;
const TIP_OFFSET_Y = -8;
export function tipPos(e) {
  return { x: e.clientX + TIP_OFFSET_X, y: e.clientY + TIP_OFFSET_Y };
}

/**
 * Format a file size in bytes to human-readable string (KB, MB, GB, etc.).
 * Uses 1024-based units to match rp.human_readable_file_size behavior.
 * Pure function.
 *
 * Examples:
 *   humanFilesize(0)         → '0B'
 *   humanFilesize(100)       → '100B'
 *   humanFilesize(1024)      → '1KB'
 *   humanFilesize(1025)      → '1.0KB'
 *   humanFilesize(10000000)  → '9.5MB'
 *   humanFilesize(1073741824) → '1GB'
 */
export function humanFilesize(bytes) {
  if (bytes === 0) return '0B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  let val = bytes;
  for (const unit of units) {
    if (Math.abs(val) < 1024 || unit === 'PB') {
      return val === Math.floor(val) ? `${val}${unit}` : `${val.toFixed(1)}${unit}`;
    }
    val /= 1024;
  }
}

/**
 * Collect all numeric fields from a video_info response into [{key, value}].
 * Iterates metadata + stats. Dynamic fields (e.g., score) are in stats
 * after normalization by the server's enrich_results().
 * Sorted by canonical field ordering (dynamic first, then FIELD_ORDER, then alpha).
 * Pure function.
 */
export function collectVideoFields(data) {
  const map = {};
  for (const source of [data.metadata, data.stats]) {
    if (!source) continue;
    for (const [k, v] of Object.entries(source)) {
      if (typeof v === 'number') map[k] = v;
    }
  }
  return sortFieldKeys(Object.keys(map)).map(k => ({ key: k, value: map[k] }));
}
