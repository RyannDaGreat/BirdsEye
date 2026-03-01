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

/**
 * Get a human-readable label for a field key.
 * Looks up from server-provided field_info first, falls back to auto-formatting.
 * Pure function.
 */
export function fieldLabel(key) {
  const info = get(fieldInfo);
  if (info.fields && info.fields[key] && info.fields[key].label) {
    return info.fields[key].label;
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
  'width', 'height', 'num_frames', 'duration', 'fps', 'file_size_mb',
  'clip_std', 'score',
  'flow_mean_magnitude', 'flow_max_magnitude', 'flow_min_magnitude', 'flow_std_magnitude', 'flow_temporal_std',
  'phash_mean_change', 'phash_max_change', 'phash_std_change', 'phash_temporal_std',
  'mean_volume', 'max_volume',
];

export function availableFields(metadataStats) {
  const keys = Object.keys(metadataStats);
  // Sort: ordered fields first, then alphabetical for the rest
  const ordered = FIELD_ORDER.filter(k => keys.includes(k));
  const rest = keys.filter(k => !FIELD_ORDER.includes(k)).sort();
  return [...ordered, ...rest].map(key => ({
    key,
    label: fieldLabel(key),
    step: fieldStep(key, metadataStats[key]),
    dtype: fieldDtype(key),
    count: metadataStats[key]?.count ?? null,
    description: fieldDescription(key),
  }));
}
