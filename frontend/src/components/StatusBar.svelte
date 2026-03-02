<script>
  import { selectedVideos, datasetInfo, showExport, pageSize, currentPage, totalResults } from '../lib/stores.js';
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher();

  $: selCount = $selectedVideos.size;
  $: total = $totalResults;
  $: totalPages = Math.max(1, Math.ceil(total / $pageSize));
  $: if ($currentPage > totalPages) $currentPage = totalPages;

  function exportSelected() { $showExport = true; dispatch('export', { mode: 'selected' }); }
  function exportAll() { $showExport = true; dispatch('export', { mode: 'all' }); }
  function clearSelection() { $selectedVideos = new Set(); }
  function prevPage() { if ($currentPage > 1) { $currentPage--; dispatch('pagechange'); } }
  function nextPage() { if ($currentPage < totalPages) { $currentPage++; dispatch('pagechange'); } }
  function onPageInput(e) {
    const v = parseInt(e.target.value);
    if (v >= 1 && v <= totalPages) { $currentPage = v; dispatch('pagechange'); }
  }
  function onPageSizeChange() { $currentPage = 1; dispatch('pagechange'); }
</script>

<div class="status-bar">
  <div class="section">
    <span>{total} results</span>
    <span>{$datasetInfo.count || 0} in dataset</span>
    {#if selCount > 0}
      <span class="sel-count">{selCount} selected</span>
    {/if}
  </div>
  <div class="section pagination">
    <button class="control" on:click={prevPage} disabled={$currentPage <= 1}
            title="Previous page"><iconify-icon icon="mdi:chevron-left" inline></iconify-icon></button>
    <input class="input-sm page-input" type="number" min="1" max={totalPages}
           bind:value={$currentPage} on:change={onPageInput}
           title="Jump to page number" />
    <span class="page-label">/ {totalPages}</span>
    <button class="control" on:click={nextPage} disabled={$currentPage >= totalPages}
            title="Next page"><iconify-icon icon="mdi:chevron-right" inline></iconify-icon></button>
    <select class="input-sm" bind:value={$pageSize} on:change={onPageSizeChange}
            title="Results per page">
      <option value={1}>1</option>
      <option value={5}>5</option>
      <option value={10}>10</option>
      <option value={25}>25</option>
      <option value={50}>50</option>
      <option value={100}>100</option>
      <option value={200}>200</option>
      <option value={500}>500</option>
      <option value={1000}>1000</option>
      <option value={2000}>2000</option>
      <option value={2500}>2500</option>
      <option value={3000}>3000</option>
      <option value={4000}>4000</option>
      <option value={5000}>5000</option>
    </select>
    <span class="page-label">per page</span>
  </div>
  <div class="section">
    <button class="control" on:click={exportAll} title="Export all video names from current search results"><iconify-icon icon="mdi:export" inline></iconify-icon> Export All</button>
    {#if selCount > 0}
      <button class="control" on:click={exportSelected} title="Export names of selected videos only"><iconify-icon icon="mdi:export" inline></iconify-icon> Export Selected</button>
      <button class="control" on:click={clearSelection} title="Deselect all videos"><iconify-icon icon="mdi:close-circle-outline" inline></iconify-icon> Clear</button>
    {/if}
  </div>
</div>

<style>
  .status-bar {
    background: var(--surface); border-bottom: 1px solid var(--border);
    padding: var(--space-sm) var(--space-2xl); display: flex; justify-content: space-between;
    align-items: center; font-size: var(--font-size-small); color: var(--text-dim); flex-shrink: 0;
  }
  .section { display: flex; gap: var(--space-md); align-items: center; }
  .sel-count { color: var(--selected); }
  .pagination { gap: var(--space-sm); }
  .page-input { width: 40px; text-align: center; }
  .page-label { font-size: var(--font-size-xs); color: var(--text-dim); }
  .control:disabled { opacity: 0.3; cursor: default; }
</style>
