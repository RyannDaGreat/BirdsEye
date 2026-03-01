<script>
  import { onMount } from 'svelte';
  import { currentDataset, currentMode, currentSort, searchQuery, currentResults, selectedVideos, datasets, metadataStats, histogramData, fieldInfo, appConfig, loading, errorMsg, filters, detailData, showFilters, pageSize, currentPage, thumbFilter, favFilter, logScale, totalResults, favorites } from './lib/stores.js';
  import { fetchDatasets, fetchMetadataStats, fetchHistograms, fetchFieldInfo, fetchConfig, searchFuzzy, searchClip, searchHull, fetchVideoInfo, fetchFavorites, toggleFavorite } from './lib/api.js';
  import { readStateFromURL, writeStateToURL } from './lib/url.js';
  import { parseSortKey } from './lib/format.js';

  import SearchHeader from './components/SearchHeader.svelte';
  import FilterPanel from './components/FilterPanel.svelte';
  import StatsPanel from './components/StatsPanel.svelte';
  import SyntaxHelp from './components/SyntaxHelp.svelte';
  import StatusBar from './components/StatusBar.svelte';
  import VideoGrid from './components/VideoGrid.svelte';
  import DetailPanel from './components/DetailPanel.svelte';
  import ExportModal from './components/ExportModal.svelte';

  let exportText = '';
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
    initialized = true;

    $datasets = await fetchDatasets();
    try {
      $appConfig = await fetchConfig();
      $fieldInfo = await fetchFieldInfo();
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
      if ($currentMode === 'fuzzy') {
        data = await searchFuzzy($currentDataset, $searchQuery, searchParams);
      } else if ($currentMode === 'clip') {
        if (!$searchQuery.trim()) {
          $loading = false;
          $errorMsg = 'Type a description for CLIP search';
          $currentResults = [];
          $totalResults = 0;
          return;
        }
        data = await searchClip($currentDataset, $searchQuery, searchParams);
      } else if ($currentMode === 'hull') {
        if ($selectedVideos.size === 0) {
          $loading = false;
          $errorMsg = 'Select videos first, then use Hull mode';
          $currentResults = [];
          $totalResults = 0;
          return;
        }
        data = await searchHull($currentDataset, $selectedVideos, searchParams);
      }

      if (data.error) {
        $errorMsg = data.error;
        $currentResults = [];
        $totalResults = 0;
      } else {
        $currentResults = data.results || [];
        $totalResults = data.total || 0;
        if (data.histograms) $histogramData = data.histograms;
      }
    } catch (e) {
      $errorMsg = e.message;
      $currentResults = [];
      $totalResults = 0;
    }
    $loading = false;
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
    $detailData = await fetchVideoInfo($currentDataset, item.video_name);
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

  function onExport(e) {
    const mode = e.detail.mode;
    if (mode === 'selected') {
      exportText = Array.from($selectedVideos).sort().join('\n');
    } else {
      exportText = $currentResults.map(r => r.video_name).join('\n');
    }
  }
</script>

<SearchHeader on:search={doSearch} on:sort={onSort} />
<FilterPanel on:search={doSearch} />
<StatsPanel />
<SyntaxHelp />
<StatusBar on:export={onExport} on:pagechange={onPageChange} />
<div class="content-row">
  <VideoGrid on:toggle={onToggle} on:detail={onDetail} on:favorite={onFavorite} />
  <DetailPanel on:favorite={onFavorite} />
</div>
<ExportModal text={exportText} />

<style>
  .content-row {
    display: flex;
    flex: 1;
    overflow: hidden;
    min-height: 0;
  }
</style>
