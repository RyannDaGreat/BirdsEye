<script>
  import { showFilters, showStats, filters, histogramData, metadataStats, logScale, hoveredItem, thumbFilter, favFilter, activeFields, hoveredFields } from '../lib/stores.js';
  import { getNestedValue } from '../lib/sort.js';
  import { availableFields, fieldTooltip } from '../lib/fields.js';
  import { createEventDispatcher } from 'svelte';
  import HistogramFilter from './widgets/HistogramFilter.svelte';

  const dispatch = createEventDispatcher();

  // Ternary cycle: any → only → none → any
  const ternaryCycle = { any: 'only', only: 'none', none: 'any' };
  function cycleThumb() { $thumbFilter = ternaryCycle[$thumbFilter] || 'any'; dispatch('search'); }
  function cycleFav()   { $favFilter   = ternaryCycle[$favFilter]   || 'any'; dispatch('search'); }

  $: thumbLabel = $thumbFilter === 'only' ? 'Only' : $thumbFilter === 'none' ? 'None' : 'Any';
  $: favLabel   = $favFilter   === 'only' ? 'Only' : $favFilter   === 'none' ? 'None' : 'Any';
  $: thumbIcon  = $thumbFilter === 'only' ? 'mdi:image-check' : $thumbFilter === 'none' ? 'mdi:image-off' : 'mdi:image-outline';
  $: favIcon    = $favFilter   === 'only' ? 'mdi:heart'       : $favFilter   === 'none' ? 'mdi:heart-off' : 'mdi:heart-outline';

  $: allFields = availableFields($metadataStats);
  // activeFields controls which histograms are visible, regardless of whether stats panel is open.
  // Once fields have been toggled (activeFields is not empty), respect the selection always.
  // Only show all fields when activeFields hasn't been initialized yet (size 0 and stats never opened).
  $: fields = $activeFields.size > 0
    ? allFields.filter(f => $activeFields.has(f.key))
    : allFields;

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

  // When activeFields changes, clear filters for any fields that are no longer active.
  // This prevents hidden fields from silently filtering results.
  $: {
    const activeKeys = new Set(fields.map(f => f.key));
    const f = { ...$filters };
    let changed = false;
    for (const k of Object.keys(f)) {
      const fieldKey = k.startsWith('min_') ? k.slice(4) : k.startsWith('max_') ? k.slice(4) : null;
      if (fieldKey && !activeKeys.has(fieldKey)) {
        delete f[k];
        changed = true;
      }
    }
    if (changed) {
      $filters = f;
      dispatch('search');
    }
  }

</script>

<div class="panel filter-panel" class:visible={$showFilters}>
  <!-- Left sidebar: controls -->
  <div class="filter-sidebar">
    <div class="section-label">Filters</div>
    <button class="log-toggle" class:active={$logScale} on:click={() => { $logScale = !$logScale; }}
            title={$logScale ? 'Switch to linear scale' : 'Switch to log scale'}>
      <iconify-icon icon="mdi:chart-line" inline></iconify-icon> {$logScale ? 'Log' : 'Lin'}
    </button>
    <button class="filter-ctrl filter-ctrl-2line" class:active={$thumbFilter === 'only'}
            class:reject={$thumbFilter === 'none'} on:click={cycleThumb}
            title="Filter by thumbnail availability">
      <span class="ctrl-top"><iconify-icon icon={thumbIcon} inline></iconify-icon> Thumb</span>
      <span class="ctrl-val">{thumbLabel}</span>
    </button>
    <button class="filter-ctrl filter-ctrl-2line" class:active={$favFilter === 'only'}
            class:reject={$favFilter === 'none'} on:click={cycleFav}
            title="Filter by favorite status">
      <span class="ctrl-top"><iconify-icon icon={favIcon} inline></iconify-icon> Fav</span>
      <span class="ctrl-val">{favLabel}</span>
    </button>
  </div>

  <!-- Dotted vertical separator -->
  <div class="filter-vsep"></div>

  <!-- Right main area: histograms -->
  <div class="filter-main">
    {#if fields.length > 0}
      <div class="filter-grid">
        {#each fields as def (def.key)}
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div on:mouseenter={() => $hoveredFields = new Set([def.key])}
               on:mouseleave={() => $hoveredFields = new Set()}>
            <HistogramFilter
              label={def.label}
              helpTip={fieldTooltip(def.key)}
              histogram={$histogramData[def.key] || null}
              useLog={$logScale}
              highlighted={$hoveredFields.has(def.key)}
              indicatorValue={$hoveredItem ? getNestedValue($hoveredItem, def.key) : null}
              bind:min={mins[def.key]}
              bind:max={maxs[def.key]}
              step={def.step}
              count={$histogramData[def.key]?.count ?? def.count}
              on:change={onFilterChange}
            />
          </div>
        {/each}
      </div>
    {:else if allFields.length > 0}
      <div class="filter-empty">
        Select fields in the Analysis panel to show filter histograms.
        <button class="control" on:click={() => $showStats = true}>
          <iconify-icon icon="mdi:chart-box-outline" inline></iconify-icon>
          {$showStats ? 'Statistics Open' : 'Open Statistics'}
        </button>
      </div>
    {:else}
      <div class="filter-empty">No numeric fields available in this dataset.</div>
    {/if}
  </div>
</div>

<style>
  .filter-panel.visible {
    display: flex !important;
    flex-direction: row;
    align-items: stretch;
    gap: 0;
    flex-wrap: nowrap;
    padding: var(--space-sm) var(--space-md);
  }

  /* Left sidebar: fixed-width column with controls, top-left aligned */
  .filter-sidebar {
    width: var(--filter-sidebar-width); flex-shrink: 0;
    display: flex; flex-direction: column; gap: var(--space-xs);
    align-items: flex-start;
  }

  /* Dotted vertical separator — stretches full height via align-items: stretch on parent */
  .filter-vsep {
    border-left: 1px dotted var(--border);
    margin: calc(-1 * var(--space-sm)) var(--space-md);
  }

  /* Right main area fills remaining space */
  .filter-main {
    flex: 1; min-width: 0;
  }

  /* Compact control buttons in sidebar */
  .filter-ctrl {
    background: var(--bg); border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: var(--space-xs) var(--space-sm);
    font-size: var(--font-size-xs); color: var(--text-dim);
    cursor: pointer; width: 100%; text-align: left;
    font-family: var(--font);
  }
  .filter-ctrl:hover { color: var(--text); border-color: var(--text-dim); }
  .filter-ctrl.active { color: var(--accent); border-color: var(--accent); }
  .filter-ctrl.reject { color: var(--selected); border-color: var(--selected); }
  .filter-ctrl-2line {
    display: flex; flex-direction: column; align-items: center; text-align: center;
  }
  .ctrl-top { white-space: nowrap; }
  .ctrl-val { font-size: var(--font-size-xxs); opacity: 0.7; }

  .filter-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: var(--space-md) var(--space-2xl);
    width: 100%;
  }

  .filter-empty {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: var(--space-md); padding: var(--space-2xl);
    color: var(--text-dim); font-size: var(--font-size-control); text-align: center;
    width: 100%;
  }
</style>
