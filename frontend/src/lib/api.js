/**
 * API client for the search backend.
 * All functions are pure (return promises, no side effects on stores).
 */

/**
 * Parse a fetch response as JSON. If the server returned an error status,
 * try to extract the error message from the JSON body before throwing.
 * Pure function (returns promise).
 */
async function checkedJson(resp) {
  const data = await resp.json().catch(() => null);
  if (!resp.ok) {
    const msg = (data && data.error) || `${resp.status} ${resp.statusText}`;
    const err = new Error(msg);
    err.hint = (data && data.hint) || '';
    throw err;
  }
  return data;
}

export async function fetchDatasets() {
  const resp = await fetch('/api/datasets');
  return checkedJson(resp);
}

export async function fetchMetadataStats(dataset) {
  const resp = await fetch(`/api/metadata_stats/${dataset}`);
  return checkedJson(resp);
}

/** Search via a named endpoint (fuzzy, clip). Pure function (returns promise). */
async function searchWithEndpoint(endpoint, dataset, query, params) {
  const filterQS = filtersToQueryString(params.filters);
  const paginationQS = paginationToQueryString(params);
  const indexQS = params.index ? `&index=${encodeURIComponent(params.index)}` : '';
  const resp = await fetch(`/api/search/${endpoint}?dataset=${dataset}&q=${encodeURIComponent(query)}${filterQS}${paginationQS}${indexQS}`);
  return checkedJson(resp);
}

export const searchFuzzy = (dataset, query, params) => searchWithEndpoint('fuzzy', dataset, query, params);
export const searchClip = (dataset, query, params) => searchWithEndpoint('clip', dataset, query, params);

/**
 * SSE-streaming version of searchClip. Sends status events to onStatus callback
 * while the server loads models / runs search, then returns the final result.
 * Falls back to normal JSON if SSE parsing fails.
 */
export async function searchClipStreaming(dataset, query, params, onStatus) {
  const filterQS = filtersToQueryString(params.filters);
  const paginationQS = paginationToQueryString(params);
  const indexQS = params.index ? `&index=${encodeURIComponent(params.index)}` : '';
  const url = `/api/search/clip?dataset=${dataset}&q=${encodeURIComponent(query)}${filterQS}${paginationQS}${indexQS}`;
  const resp = await fetch(url, { headers: { 'Accept': 'text/event-stream' } });

  if (!resp.ok) {
    const data = await resp.json().catch(() => null);
    const err = new Error((data && data.error) || `${resp.status} ${resp.statusText}`);
    err.hint = (data && data.hint) || '';
    throw err;
  }

  // If server didn't return SSE (e.g., error responses are still JSON), parse as JSON
  const contentType = resp.headers.get('Content-Type') || '';
  if (!contentType.includes('text/event-stream')) {
    return resp.json();
  }

  // Parse SSE stream
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let result = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // Parse complete SSE events (double newline delimited)
    let idx;
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);

      // Extract data line from SSE block
      let dataStr = '';
      for (const line of block.split('\n')) {
        if (line.startsWith('data: ')) {
          dataStr += line.slice(6);
        }
      }
      if (!dataStr) continue;

      const parsed = JSON.parse(dataStr);
      if (parsed.type === 'status') {
        if (onStatus) onStatus(parsed.message);
      } else if (parsed.type === 'result') {
        result = parsed.data;
      }
    }
  }

  if (result && result.error) {
    const err = new Error(result.error);
    err.hint = result.hint || '';
    throw err;
  }
  return result;
}

export async function searchHull(dataset, selected, { page, pageSize, sort, sortDir, thumbFilter, favFilter, randomSeed, filters }) {
  const resp = await fetch('/api/search/hull', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      dataset,
      selected: Array.from(selected),
      thumb_filter: thumbFilter || 'any',
      fav_filter: favFilter || 'any',
      page, page_size: pageSize,
      sort: sort || '', sort_dir: sortDir || 'desc',
      random_seed: randomSeed || 0,
      ...filters,
    }),
  });
  return checkedJson(resp);
}

export async function fetchConfig() {
  const resp = await fetch('/api/config');
  return checkedJson(resp);
}

export async function fetchFieldInfo() {
  const resp = await fetch('/api/field_info');
  return checkedJson(resp);
}

export async function fetchEmbeddingModels() {
  const resp = await fetch('/api/embedding_models');
  return checkedJson(resp);
}

export async function fetchHistograms(dataset, bins = 60) {
  const resp = await fetch(`/api/histograms/${dataset}?bins=${bins}`);
  return checkedJson(resp);
}

export async function fetchVideoInfo(dataset, videoName) {
  const resp = await fetch(`/api/video_info/${dataset}/${videoName}`);
  return checkedJson(resp);
}

export async function fetchFavorites(dataset) {
  const resp = await fetch(`/api/favorites/${dataset}`);
  const data = await checkedJson(resp);
  return data.favorites || [];
}

export async function toggleFavorite(dataset, videoName, action) {
  const resp = await fetch(`/api/favorites/${dataset}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ video_name: videoName, action }),
  });
  return checkedJson(resp);
}

/**
 * Fetch all matching video names and paths for current search (no pagination).
 * Used by "Export All" to get every result, not just the current page.
 * Pure function (returns promise of {names: string[], paths: string[]}).
 */
export async function exportAllNamesAndPaths(dataset, query, mode, params) {
  const filterQS = filtersToQueryString(params.filters);
  const sortQS = params.sort ? `&sort=${encodeURIComponent(params.sort)}` : '';
  const sortDirQS = params.sortDir ? `&sort_dir=${params.sortDir}` : '';
  const thumbQS = params.thumbFilter && params.thumbFilter !== 'any' ? `&thumb_filter=${params.thumbFilter}` : '';
  const favQS = params.favFilter && params.favFilter !== 'any' ? `&fav_filter=${params.favFilter}` : '';
  const indexQS = params.index ? `&index=${encodeURIComponent(params.index)}` : '';
  const resp = await fetch(`/api/export/names?dataset=${dataset}&q=${encodeURIComponent(query)}&mode=${mode}${indexQS}${filterQS}${sortQS}${sortDirQS}${thumbQS}${favQS}`);
  const data = await checkedJson(resp);
  return { names: data.names || [], paths: data.paths || [] };
}

/**
 * Resolve selected video names to their sample directory paths.
 * Used by "Export Selected" to get paths without re-running search.
 * Pure function (returns promise of {names: string[], paths: string[]}).
 */
export async function exportResolve(dataset, videoNames) {
  const resp = await fetch('/api/export/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset, video_names: videoNames }),
  });
  return checkedJson(resp);
}

/**
 * Download a zip of selected sample directories.
 * Triggers browser download of a .zip file.
 */
import { downloadStatus } from './stores.js';

export async function downloadSamples(dataset, videoNames) {
  downloadStatus.set(`Zipping ${videoNames.length} sample${videoNames.length > 1 ? 's' : ''}.`);
  try {
    const resp = await fetch('/api/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset, video_names: videoNames }),
    });
    if (!resp.ok) {
      const data = await resp.json().catch(() => null);
      downloadStatus.set('');
      throw new Error((data && data.error) || `${resp.status} ${resp.statusText}`);
    }
    downloadStatus.set('Downloading zip.');
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'birdseye_samples.zip';
    a.click();
    URL.revokeObjectURL(url);
  } finally {
    downloadStatus.set('');
  }
}

/**
 * Fetch sampled + quantized scatter data for a dataset.
 * Returns {fields: string[], ranges: {field: [min, max]}, samples: number[][]}.
 * Pure function (returns promise).
 */
export async function fetchScatterData(dataset, sampleSize = 5000, fields = null) {
  let url = `/api/scatter_data/${dataset}?sample_size=${sampleSize}`;
  if (fields) url += `&fields=${fields.join(',')}`;
  const resp = await fetch(url);
  return checkedJson(resp);
}

/** Convert filters object to query string params. Pure function. */
function filtersToQueryString(filters) {
  return Object.entries(filters || {})
    .filter(([, v]) => v !== '' && v !== undefined && v !== null)
    .map(([k, v]) => `&${k}=${encodeURIComponent(v)}`)
    .join('');
}

/** Convert pagination/sort/ternary params to query string. Pure function. */
function paginationToQueryString({ page, pageSize, sort, sortDir, thumbFilter, favFilter, randomSeed }) {
  let qs = '';
  if (page) qs += `&page=${page}`;
  if (pageSize) qs += `&page_size=${pageSize}`;
  if (sort) qs += `&sort=${encodeURIComponent(sort)}`;
  if (sortDir) qs += `&sort_dir=${sortDir}`;
  if (thumbFilter && thumbFilter !== 'any') qs += `&thumb_filter=${thumbFilter}`;
  if (favFilter && favFilter !== 'any') qs += `&fav_filter=${favFilter}`;
  if (randomSeed) qs += `&random_seed=${randomSeed}`;
  return qs;
}
