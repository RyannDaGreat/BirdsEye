/**
 * API client for the search backend.
 * All functions are pure (return promises, no side effects on stores).
 */

async function checkedJson(resp) {
  if (!resp.ok) throw new Error(`API error: ${resp.status} ${resp.statusText}`);
  return resp.json();
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
  const resp = await fetch(`/api/search/${endpoint}?dataset=${dataset}&q=${encodeURIComponent(query)}${filterQS}${paginationQS}`);
  return checkedJson(resp);
}

export const searchFuzzy = (dataset, query, params) => searchWithEndpoint('fuzzy', dataset, query, params);
export const searchClip = (dataset, query, params) => searchWithEndpoint('clip', dataset, query, params);

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
