/**
 * Single source of truth for available numeric fields.
 *
 * Labels and descriptions come from the server (/api/field_info),
 * which aggregates Python plugin FIELDS + metadata field definitions.
 * No hardcoded labels in the frontend.
 *
 * All functions are pure.
 */

import { get } from 'svelte/store';
import { fieldInfo } from './stores.js';

/** Unicode marker prepended to dynamic field labels (computed on-the-fly, not stored). */
const DYNAMIC_MARKER = '\u2726'; // ✦

/**
 * Get a human-readable label for a field key.
 * Looks up from server-provided field_info first, falls back to auto-formatting.
 * Dynamic fields (server-flagged) get the ✦ marker prepended.
 * Pure function.
 */
export function fieldLabel(key) {
  const info = get(fieldInfo);
  if (info.fields && info.fields[key]) {
    const f = info.fields[key];
    const label = f.label || key.replace(/_/g, ' ');
    return f.dynamic ? `${DYNAMIC_MARKER} ${label}` : label;
  }
  return key.replace(/_/g, ' ');
}

/**
 * Get the description for a field key.
 * Pure function.
 */
export function fieldDescription(key) {
  const info = get(fieldInfo);
  if (info.fields && info.fields[key] && info.fields[key].description) {
    return info.fields[key].description;
  }
  return '';
}

/**
 * Get the source plugin name for a field key (e.g., "Ingest", "Pexels").
 * Pure function.
 */
export function fieldSource(key) {
  const info = get(fieldInfo);
  if (info.fields && info.fields[key] && info.fields[key].source) {
    return info.fields[key].source;
  }
  return '';
}

/**
 * Build the HTML tooltip string for a field key.
 * Shows label (bold), description, and source plugin (italic, 50% opacity).
 * Returns empty string if no description exists.
 * Pure function.
 *
 * @param {string} key - The field key (e.g., "duration", "flow_mean_magnitude")
 * @returns {string} HTML string for tooltip, or '' if no description
 *
 * >>> fieldTooltip('nonexistent_field_xyz')  // returns ''
 */
export function fieldTooltip(key) {
  const desc = fieldDescription(key);
  if (!desc) return '';
  const source = fieldSource(key);
  const sourceHtml = source
    ? `<br/><span style="opacity:0.5;font-style:italic">Source: ${source} (${key})</span>`
    : '';
  return `<strong>${fieldLabel(key)}</strong><br/>${desc}${sourceHtml}`;
}

/**
 * Get the dtype ("int" or "float") for a field from server-provided field_info.
 * Pure function.
 */
export function fieldDtype(key) {
  const info = get(fieldInfo);
  if (info.fields && info.fields[key] && info.fields[key].dtype) {
    return info.fields[key].dtype;
  }
  return 'float'; // default to float for unknown fields
}

/**
 * Compute input step for a field based on dtype and range.
 * Integer fields always use step=1. Float fields scale by range.
 * Pure function.
 */
export function fieldStep(key, stats) {
  const dtype = fieldDtype(key);
  if (dtype === 'int') return 1;
  if (!stats) return 0.01;
  const range = stats.max - stats.min;
  if (range <= 1) return 0.001;
  if (range <= 10) return 0.01;
  if (range <= 100) return 0.1;
  return 1;
}

/**
 * Derive the list of available numeric fields from metadataStats.
 * Returns [{key, label, step, description}] for each field.
 * Single source used by filters, sort, detail panel.
 * Pure function.
 */
/** Preferred field ordering. Listed fields come first, rest follow alphabetically. */
const FIELD_ORDER = [
  'height', 'width', 'duration', 'num_frames', 'file_size_mb',
  'fps', 'clip_std', 'score',
  'flow_mean_magnitude', 'flow_max_magnitude', 'flow_min_magnitude', 'flow_std_magnitude', 'flow_temporal_std',
  'phash_mean_change', 'phash_max_change', 'phash_std_change', 'phash_temporal_std',
  'mean_volume', 'max_volume',
];

/**
 * Check if a field is dynamic (computed on-the-fly, not stored on disk).
 * Pure function.
 */
export function isDynamicField(key) {
  const info = get(fieldInfo);
  return !!(info.fields && info.fields[key] && info.fields[key].dynamic);
}

/**
 * Sort field keys by preferred ordering.
 * Dynamic fields come first, then FIELD_ORDER, then alphabetical remainder.
 * Pure function.
 *
 * @param {string[]} keys - field keys to sort
 * @returns {string[]} sorted keys
 *
 * >>> sortFieldKeys(['fps', 'height', 'width', 'zzz', 'duration'])
 * ['height', 'width', 'duration', 'fps', 'zzz']
 */
export function sortFieldKeys(keys) {
  const dynamic = keys.filter(k => isDynamicField(k));
  const nonDynamic = keys.filter(k => !isDynamicField(k));
  const ordered = FIELD_ORDER.filter(k => nonDynamic.includes(k));
  const rest = nonDynamic.filter(k => !FIELD_ORDER.includes(k)).sort();
  return [...dynamic, ...ordered, ...rest];
}

export function availableFields(metadataStats) {
  return sortFieldKeys(Object.keys(metadataStats)).map(key => ({
    key,
    label: fieldLabel(key),
    step: fieldStep(key, metadataStats[key]),
    dtype: fieldDtype(key),
    count: metadataStats[key]?.count ?? null,
    description: fieldDescription(key),
  }));
}
