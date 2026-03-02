<script>
  import { currentDataset, currentMode, currentSort, searchQuery, datasets, metadataStats, showFilters, showStats, showHelp, embeddingModels } from '../lib/stores.js';
  import { availableFields } from '../lib/fields.js';
  import { parseSortKey, dynamicFieldLabel } from '../lib/format.js';
  import { createEventDispatcher } from 'svelte';
  import ReloadIndicator from './ReloadIndicator.svelte';

  const dispatch = createEventDispatcher();

  // Dynamic modes: fuzzy + one per embedding model + hull (if any model exists)
  $: modelPrefixes = Object.keys($embeddingModels);
  $: modes = ['fuzzy', ...modelPrefixes, ...(modelPrefixes.length ? ['hull'] : [])];

  function modeLabel(mode) {
    if (mode === 'fuzzy') return 'Fuzzy';
    if (mode === 'hull') return 'Hull';
    const m = $embeddingModels[mode];
    return m ? mode.toUpperCase() : mode;
  }

  function modePlaceholder(mode) {
    if (mode === 'fuzzy') return "FZF search: cat dog | !rain | 'blue sky'";
    if (mode === 'hull') return 'Hull search from selected videos';
    return 'Describe what you want to see...';
  }

  function modeTooltip(mode) {
    if (mode === 'fuzzy') return 'Text search through captions (FZF extended syntax)';
    if (mode === 'hull') return 'Centroid search: computes the average embedding of your selected videos, then finds videos most similar to that average. Works because similar videos cluster in embedding space.';
    const m = $embeddingModels[mode];
    return m ? `Semantic search via ${m.name}: ${m.description}` : 'Semantic search';
  }

  let debounceTimer;

  function onInput() {
    clearTimeout(debounceTimer);
    const delay = ($currentMode in $embeddingModels) ? 500 : 150;
    debounceTimer = setTimeout(() => dispatch('search'), delay);
  }

  function onKeydown(e) {
    if (e.key === 'Enter') { clearTimeout(debounceTimer); dispatch('search'); }
  }

  function setMode(mode) {
    $currentMode = mode;
    dispatch('search');
  }

  let sortField = '';
  let sortDesc = true;
  let _lastSort = '';  // Track external changes to avoid reactive loops

  // Reactive: sync sortField/sortDesc when $currentSort changes externally (e.g., URL restore)
  $: if ($currentSort !== _lastSort) {
    _lastSort = $currentSort;
    const { key, direction } = parseSortKey($currentSort);
    sortField = key;
    sortDesc = direction !== 'asc';
  }

  function updateSort() {
    if (!sortField) { $currentSort = ''; }
    else if (sortField === 'random') { $currentSort = 'random'; }
    else { $currentSort = `${sortField}_${sortDesc ? 'desc' : 'asc'}`; }
    _lastSort = $currentSort;
    dispatch('sort');
  }

  function toggleDirection() {
    sortDesc = !sortDesc;
    updateSort();
  }

  function onSortFieldChange() { updateSort(); }

  $: dynamicFields = availableFields($metadataStats);
</script>

<div class="header">
  <h1><span class="logo-wrap"><span class="logo" title="BirdsEye"></span></span> BirdsEye</h1>
  <ReloadIndicator />
  <select class="control" bind:value={$currentDataset} on:change={() => dispatch('datasetchange')} title="Select dataset to search">
    {#each Object.entries($datasets) as [name, info]}
      <option value={name}>{info.human_name || name} ({info.count.toLocaleString()})</option>
    {/each}
  </select>
  <div class="search-container">
    <div class="search-wrap">
      <!-- svelte-ignore a11y-autofocus -->
      <input class="control search" bind:value={$searchQuery}
             placeholder={modePlaceholder($currentMode)}
             title="Search query — type and press Enter"
             on:input={onInput} on:keydown={onKeydown} autofocus />
      {#if $searchQuery}
        <button class="clear-btn search-x" title="Clear search query" on:click={() => { $searchQuery = ''; dispatch('search'); }}>&times;</button>
      {/if}
    </div>
    <div class="mode-tabs">
      {#each modes as mode}
        <button class="mode-tab" class:active={$currentMode === mode}
                title={modeTooltip(mode)}
                on:click={() => setMode(mode)}>{modeLabel(mode)}</button>
      {/each}
    </div>
  </div>
  <select class="control" bind:value={sortField} on:change={onSortFieldChange} title="Sort results by a field">
    <option value="">Unsorted</option>
    <option value="random">Random</option>
    <option value="score">{dynamicFieldLabel('CLIP Score')}</option>
    <option value="name">Name</option>
    {#each dynamicFields as f}
      <option value={f.key}>{f.label}</option>
    {/each}
  </select>
  <button class="control" on:click={toggleDirection}
          title={sortDesc ? 'Sorted descending (high first) — click to reverse' : 'Sorted ascending (low first) — click to reverse'}>
    <iconify-icon icon={sortDesc ? 'mdi:sort-descending' : 'mdi:sort-ascending'} inline></iconify-icon>
  </button>
  <button class="control" class:active-toggle={$showFilters} on:click={() => $showFilters = !$showFilters} title="Toggle filter panel with histogram range selectors"><iconify-icon icon="mdi:filter-variant" inline></iconify-icon> Filters</button>
  <button class="control" class:active-toggle={$showStats} on:click={() => $showStats = !$showStats} title="Toggle aggregate statistics for current results and selection"><iconify-icon icon="mdi:chart-bar" inline></iconify-icon> Stats</button>
  <button class="control" class:active-toggle={$showHelp} on:click={() => $showHelp = !$showHelp} title="Help &amp; dataset info"><iconify-icon icon="mdi:help-circle-outline" inline></iconify-icon></button>
</div>

<style>
  .header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: var(--space-lg) var(--space-2xl);
    display: flex;
    align-items: center;
    gap: var(--space-xl);
    flex-shrink: 0;
  }
  h1 { font-size: var(--space-xl); font-weight: 600; color: var(--accent); white-space: nowrap; display: flex; align-items: center; gap: var(--space-sm); }
  .logo-wrap {
    display: inline-block; width: 1.2em; height: 1.2em; position: relative; flex-shrink: 0; margin-right: 15px;
  }
  .logo {
    position: absolute; width: 3.25em; height: 3.25em;
    top: 50%; left: 50%; transform: translate(-50%, -50%);
    background-color: currentColor;
    -webkit-mask-image: url('../assets/birdseye.svg');
    mask-image: url('../assets/birdseye.svg');
    -webkit-mask-size: contain; mask-size: contain;
    -webkit-mask-repeat: no-repeat; mask-repeat: no-repeat;
    -webkit-mask-position: center; mask-position: center;
    pointer-events: none;
  }
  .search-container { flex: 1; display: flex; gap: var(--space-md); align-items: center; }
  .search-wrap { flex: 1; position: relative; display: flex; }
  .search-wrap .search-x {
    position: absolute; right: var(--space-md); top: 50%; transform: translateY(-50%);
  }
  .mode-tabs {
    display: flex; gap: var(--space-xs); background: var(--bg);
    border-radius: var(--radius); padding: var(--space-xs);
    height: var(--control-height);
  }
  .mode-tab {
    padding: 0 var(--space-lg); border: none; background: none; color: var(--text-dim);
    font-family: var(--font); font-size: var(--font-size-control); cursor: pointer;
    border-radius: calc(var(--radius) - var(--space-xs)); transition: all 0.15s; white-space: nowrap;
    line-height: calc(var(--control-height) - var(--space-xs) * 2);
  }
  .mode-tab.active { background: var(--accent); color: #fff; }
  .mode-tab:hover:not(.active) { color: var(--text); background: var(--surface2); }
</style>
