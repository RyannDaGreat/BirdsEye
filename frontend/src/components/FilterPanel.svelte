<script>
  import { showFilters, filters, histogramData, metadataStats, logScale, hoveredItem, thumbFilter, favFilter } from '../lib/stores.js';
  import { getNestedValue } from '../lib/sort.js';
  import { availableFields } from '../lib/fields.js';
  import { createEventDispatcher } from 'svelte';
  import HistogramFilter from './widgets/HistogramFilter.svelte';
  import TernaryFilter from './widgets/TernaryFilter.svelte';

  const dispatch = createEventDispatcher();

  $: fields = availableFields($metadataStats);

  let mins = {};
  let maxs = {};

  // Reactive: rebuild mins/maxs whenever the filters store changes (e.g., from URL restore)
  $: {
    const newMins = {};
    const newMaxs = {};
    const f = $filters || {};
    for (const [k, v] of Object.entries(f)) {
      if (k.startsWith('min_')) newMins[k.slice(4)] = v;
      if (k.startsWith('max_')) newMaxs[k.slice(4)] = v;
    }
    mins = newMins;
    maxs = newMaxs;
  }

  function onFilterChange() {
    const f = {};
    for (const def of fields) {
      if (mins[def.key] !== undefined && mins[def.key] !== '') f[`min_${def.key}`] = mins[def.key];
      if (maxs[def.key] !== undefined && maxs[def.key] !== '') f[`max_${def.key}`] = maxs[def.key];
    }
    $filters = f;
    dispatch('search');
  }

  function onThumbChange(e) { $thumbFilter = e.detail; dispatch('search'); }
  function onFavChange(e) { $favFilter = e.detail; dispatch('search'); }
</script>

<div class="panel filter-panel" class:visible={$showFilters}>
  <div class="filter-grid">
    {#each fields as def (def.key)}
      <HistogramFilter
        label={def.label}
        description={def.description || ''}
        histogram={$histogramData[def.key] || null}
        useLog={$logScale}
        indicatorValue={$hoveredItem ? getNestedValue($hoveredItem, def.key) : null}
        bind:min={mins[def.key]}
        bind:max={maxs[def.key]}
        step={def.step}
        count={$histogramData[def.key]?.count ?? def.count}
        on:change={onFilterChange}
      />
    {/each}
  </div>
  <div class="filter-toolbar">
    <button class="control" on:click={() => $logScale = !$logScale}
            title={$logScale ? 'Switch to linear Y-axis' : 'Switch to logarithmic Y-axis'}>
      <iconify-icon icon="mdi:chart-line" inline></iconify-icon>
      {$logScale ? 'Log Y' : 'Linear Y'}
    </button>
    <TernaryFilter
      bind:value={$thumbFilter}
      labelAny="Thumb: Any"
      labelOnly="Thumb: Only"
      labelNone="Thumb: None"
      iconAny="mdi:image-outline"
      iconOnly="mdi:image-check"
      iconNone="mdi:image-off"
      title="Filter by thumbnail availability"
      on:change={onThumbChange}
    />
    <TernaryFilter
      bind:value={$favFilter}
      labelAny="Fav: Any"
      labelOnly="Fav: Only"
      labelNone="Fav: None"
      iconAny="mdi:heart-outline"
      iconOnly="mdi:heart"
      iconNone="mdi:heart-off"
      title="Filter by favorite status"
      on:change={onFavChange}
    />
  </div>
</div>

<style>
  .filter-panel.visible {
    display: flex !important;
    flex-direction: column;
    gap: var(--space-md);
  }

  .filter-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: var(--space-md) var(--space-2xl);
    width: 100%;
  }

  .filter-toolbar {
    display: flex;
    gap: var(--space-md);
    justify-content: flex-end;
  }
</style>
