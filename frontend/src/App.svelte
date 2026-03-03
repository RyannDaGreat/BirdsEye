<script>
  import { onMount } from 'svelte';
  import { currentDataset, currentMode, currentSort, searchQuery, currentResults, selectedVideos, datasets, metadataStats, histogramData, fieldInfo, appConfig, loading, searchStatus, errorMsg, errorHint, filters, detailData, showFilters, pageSize, currentPage, thumbFilter, favFilter, logScale, totalResults, favorites, embeddingModels, statsHeight } from './lib/stores.js';
  import { fetchDatasets, fetchMetadataStats, fetchHistograms, fetchFieldInfo, fetchConfig, searchFuzzy, searchClipStreaming, searchHull, fetchVideoInfo, fetchFavorites, toggleFavorite, fetchEmbeddingModels, exportAllNamesAndPaths, exportResolve, downloadSamples } from './lib/api.js';
  import { readStateFromURL, writeStateToURL } from './lib/url.js';
  import { parseSortKey } from './lib/format.js';
  import { isDynamicField } from './lib/fields.js';

  import SearchHeader from './components/SearchHeader.svelte';
  import FilterPanel from './components/FilterPanel.svelte';
  import StatsPanel from './components/StatsPanel.svelte';
  import SyntaxHelp from './components/SyntaxHelp.svelte';
  import StatusBar from './components/StatusBar.svelte';
  import VideoGrid from './components/VideoGrid.svelte';
  import DetailPanel from './components/DetailPanel.svelte';
  import ExportModal from './components/ExportModal.svelte';

  let exportNames = [];
  let exportPaths = [];
  let exportLoading = false;
  let initialized = false;
  let randomSeed = Date.now();

  // Sync stores → URL whenever relevant state changes (only after init)
  $: if (initialized) writeStateToURL({
    searchQuery: $searchQuery,
    currentMode: $currentMode,
    currentDataset: $currentDataset,
    currentSort: $currentSort,
    filters: $filters,
    currentPage: $currentPage,
    pageSize: $pageSize,
    thumbFilter: $thumbFilter,
    favFilter: $favFilter,
    logScale: $logScale,
    showFilters: $showFilters,
    statsHeight: $statsHeight,
  });

  onMount(async () => {
    // Restore state from URL before first search
    const urlState = readStateFromURL();
    if (urlState.searchQuery !== undefined) $searchQuery = urlState.searchQuery;
    if (urlState.currentMode) $currentMode = urlState.currentMode;
    if (urlState.currentDataset) $currentDataset = urlState.currentDataset;
    if (urlState.currentSort) $currentSort = urlState.currentSort;
    if (urlState.filters) { $filters = urlState.filters; $showFilters = true; }
    if (urlState.currentPage) $currentPage = urlState.currentPage;
    if (urlState.pageSize) $pageSize = urlState.pageSize;
    if (urlState.thumbFilter) $thumbFilter = urlState.thumbFilter;
    if (urlState.favFilter) $favFilter = urlState.favFilter;
    if (urlState.logScale !== undefined) $logScale = urlState.logScale;
    if (urlState.showFilters !== undefined) $showFilters = urlState.showFilters;
    if (urlState.statsHeight) $statsHeight = urlState.statsHeight;
    initialized = true;

    $datasets = await fetchDatasets();
    try {
      $appConfig = await fetchConfig();
      $fieldInfo = await fetchFieldInfo();
      $embeddingModels = await fetchEmbeddingModels();
      $metadataStats = await fetchMetadataStats($currentDataset);
      $histogramData = await fetchHistograms($currentDataset);
      const favList = await fetchFavorites($currentDataset);
      $favorites = new Set(favList);
    } catch (e) {
      console.error('Init fetch failed:', e);
    }
    doSearch();
  });

  async function doSearch(resetPage = true) {
    $loading = true;
    $errorMsg = '';
    $errorHint = '';
    $searchStatus = '';
    if (resetPage) $currentPage = 1;

    const { key: sortKey, direction: sortDir } = parseSortKey($currentSort);
    const searchParams = {
      page: $currentPage,
      pageSize: $pageSize,
      sort: sortKey,
      sortDir,
      thumbFilter: $thumbFilter,
      favFilter: $favFilter,
      randomSeed,
      filters: $filters,
    };

    try {
      let data;
      const isEmbeddingMode = $currentMode in $embeddingModels;
      if ($currentMode === 'fuzzy') {
        data = await searchFuzzy($currentDataset, $searchQuery, searchParams);
      } else if (isEmbeddingMode) {
        if (!$searchQuery.trim()) {
          $loading = false;
          $errorMsg = 'No search query entered.';
          $errorHint = 'Type a description of what you\'re looking for — semantic search matches your text against the visual content of each video.';
          $currentResults = [];
          $totalResults = 0;
          return;
        }
        data = await searchClipStreaming($currentDataset, $searchQuery, { ...searchParams, index: $currentMode }, (msg) => { $searchStatus = msg; });
      } else if ($currentMode === 'hull') {
        if ($selectedVideos.size === 0) {
          $loading = false;
          $errorMsg = 'No videos selected for hull search.';
          $errorHint = 'Hull search finds videos similar to your selection. Click on video thumbnails to select them first, then switch to Hull mode.';
          $currentResults = [];
          $totalResults = 0;
          return;
        }
        data = await searchHull($currentDataset, $selectedVideos, searchParams);
      }

      if (data.error) {
        $errorMsg = data.error;
        $errorHint = data.hint || '';
        $currentResults = [];
        $totalResults = 0;
      } else {
        $currentResults = data.results || [];
        $totalResults = data.total || 0;
        if (data.histograms) {
          $histogramData = data.histograms;
          // Augment metadataStats with dynamic fields from result histograms.
          // Static fields (from server) already have stable dataset-wide ranges — skip them.
          // Dynamic fields (e.g., score) only exist in results, so we track their range here.
          // Range only EXPANDS (min of mins, max of maxes) to prevent the ratchet problem:
          // filtering to a narrow range must not shrink the x-axis, or handles lock to edges.
          const augmented = { ...$metadataStats };
          let changed = false;
          for (const [key, hist] of Object.entries(data.histograms)) {
            if (!isDynamicField(key)) continue;
            const prev = augmented[key];
            if (!prev) {
              augmented[key] = { min: hist.lo, max: hist.hi, count: hist.count };
              changed = true;
            } else {
              const newMin = Math.min(prev.min, hist.lo);
              const newMax = Math.max(prev.max, hist.hi);
              const newCount = Math.max(prev.count, hist.count);
              if (newMin !== prev.min || newMax !== prev.max || newCount !== prev.count) {
                augmented[key] = { min: newMin, max: newMax, count: newCount };
                changed = true;
              }
            }
          }
          if (changed) $metadataStats = augmented;
        }
      }
    } catch (e) {
      $errorMsg = e.message;
      $errorHint = e.hint || '';
      $currentResults = [];
      $totalResults = 0;
    }
    $loading = false;
    $searchStatus = '';
  }

  async function onReload() {
    // Server already re-read cache via /api/reload. Now re-fetch all frontend stores.
    try {
      $metadataStats = await fetchMetadataStats($currentDataset);
      $histogramData = await fetchHistograms($currentDataset);
      $fieldInfo = await fetchFieldInfo();
      $embeddingModels = await fetchEmbeddingModels();
      const favList = await fetchFavorites($currentDataset);
      $favorites = new Set(favList);
    } catch (e) {
      console.error('Reload re-fetch failed:', e);
    }
    doSearch();
  }

  async function onDatasetChange() {
    try {
      $metadataStats = await fetchMetadataStats($currentDataset);
      $histogramData = await fetchHistograms($currentDataset);
      const favList = await fetchFavorites($currentDataset);
      $favorites = new Set(favList);
    } catch (e) {
      console.error('Dataset change fetch failed:', e);
    }
    doSearch();
  }

  function onSort() {
    if ($currentSort === 'random') randomSeed = Date.now();
    doSearch();
  }

  function onPageChange() {
    doSearch(false);
  }

  function onToggle(e) {
    const name = e.detail;
    const s = new Set($selectedVideos);
    if (s.has(name)) s.delete(name);
    else s.add(name);
    $selectedVideos = s;
  }

  async function onDetail(e) {
    const item = e.detail;
    const info = await fetchVideoInfo($currentDataset, item.video_name);
    // Merge dynamic fields from the search result item into the detail data's stats.
    // Server normalizes dynamic fields into item.stats; video_info endpoint doesn't
    // have them (it doesn't know the query), so we carry them over from the result.
    if (item.stats) {
      info.stats = { ...(info.stats || {}), ...item.stats };
    }
    $detailData = info;
  }

  async function onFavorite(e) {
    const videoName = e.detail;
    const isFav = $favorites.has(videoName);
    const action = isFav ? 'remove' : 'add';
    await toggleFavorite($currentDataset, videoName, action);
    const s = new Set($favorites);
    if (isFav) s.delete(videoName); else s.add(videoName);
    $favorites = s;
  }

  async function onDownload() {
    if ($selectedVideos.size === 0) return;
    await downloadSamples($currentDataset, Array.from($selectedVideos));
  }

  async function onExport(e) {
    const mode = e.detail.mode;
    exportLoading = true;
    exportNames = [];
    exportPaths = [];
    if (mode === 'selected') {
      const result = await exportResolve($currentDataset, Array.from($selectedVideos));
      exportNames = result.names;
      exportPaths = result.paths;
    } else {
      const { key: sortKey, direction: sortDir } = parseSortKey($currentSort);
      const result = await exportAllNamesAndPaths($currentDataset, $searchQuery, $currentMode, {
        sort: sortKey, sortDir,
        thumbFilter: $thumbFilter, favFilter: $favFilter,
        filters: $filters, index: $currentMode,
      });
      exportNames = result.names;
      exportPaths = result.paths;
    }
    exportLoading = false;
  }
</script>

<SearchHeader on:search={doSearch} on:sort={onSort} on:datasetchange={onDatasetChange} on:reload={onReload} />
<FilterPanel on:search={doSearch} />
<StatsPanel />
<SyntaxHelp />
<StatusBar on:export={onExport} on:pagechange={onPageChange} on:download={onDownload} />
<div class="content-row">
  <VideoGrid on:toggle={onToggle} on:detail={onDetail} on:favorite={onFavorite} />
  <DetailPanel on:favorite={onFavorite} />
</div>
<ExportModal names={exportNames} paths={exportPaths} loading={exportLoading} />

<style>
  .content-row {
    display: flex;
    flex: 1;
    overflow: hidden;
    min-height: 0;
  }
</style>
