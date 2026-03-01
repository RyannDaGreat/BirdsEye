/**
 * URL state synchronization.
 *
 * This is the ONLY place URL params are read or written.
 * Syncs view state (query, mode, sort, filters, quality, dataset) to/from
 * the URL query string so that links are shareable.
 *
 * Uses history.replaceState to avoid polluting browser back-button history.
 */

/**
 * Read all view state from the current URL query string.
 * Returns a plain object with keys matching store names.
 * Pure function (reads from window.location).
 */
export function readStateFromURL() {
  const params = new URLSearchParams(window.location.search);
  const state = {};

  if (params.has('q')) state.searchQuery = params.get('q');
  if (params.has('mode')) state.currentMode = params.get('mode');
  if (params.has('dataset')) state.currentDataset = params.get('dataset');
  if (params.has('sort')) state.currentSort = params.get('sort');
  if (params.has('page')) state.currentPage = parseInt(params.get('page'));
  if (params.has('pageSize')) state.pageSize = parseInt(params.get('pageSize'));
  if (params.has('thumb')) state.thumbFilter = params.get('thumb');
  if (params.has('fav')) state.favFilter = params.get('fav');
  if (params.has('logY')) state.logScale = params.get('logY') === '1';
  if (params.has('filters')) state.showFilters = params.get('filters') === '1';

  // Collect all min_*/max_* filter params
  const filters = {};
  for (const [key, val] of params.entries()) {
    if ((key.startsWith('min_') || key.startsWith('max_')) && val !== '') {
      filters[key] = val;
    }
  }
  if (Object.keys(filters).length > 0) state.filters = filters;

  return state;
}

/**
 * Write view state to the URL query string via history.replaceState.
 * Only includes non-default values to keep URLs clean.
 */
export function writeStateToURL({ searchQuery, currentMode, currentDataset, currentSort, filters, currentPage, pageSize, thumbFilter, favFilter, logScale, showFilters }) {
  const params = new URLSearchParams();

  if (searchQuery) params.set('q', searchQuery);
  if (currentMode && currentMode !== 'fuzzy') params.set('mode', currentMode);
  if (currentDataset && currentDataset !== 'pexels') params.set('dataset', currentDataset);
  if (currentSort) params.set('sort', currentSort);
  if (currentPage && currentPage > 1) params.set('page', currentPage);
  if (pageSize && pageSize !== 200) params.set('pageSize', pageSize);
  if (thumbFilter && thumbFilter !== 'any') params.set('thumb', thumbFilter);
  if (favFilter && favFilter !== 'any') params.set('fav', favFilter);
  if (logScale === false) params.set('logY', '0');
  if (showFilters) params.set('filters', '1');

  // Add filter params
  if (filters) {
    for (const [key, val] of Object.entries(filters)) {
      if (val !== '' && val !== undefined && val !== null) {
        params.set(key, val);
      }
    }
  }

  const qs = params.toString();
  const url = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
  history.replaceState(null, '', url);
}
