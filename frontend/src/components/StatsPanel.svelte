<!--
  Statistics panel: three resizable columns side by side.
  Left: Summary (vertical field bar list). Center: Scatterplot Matrix. Right: Words.
  Draggable vertical splits between columns.
-->
<script>
  import { showStats, currentResults, selectedVideos, statsSourceA, statsSourceB, activeFields, statsHeight } from '../lib/stores.js';
  import { collectNumericFields, summarize } from '../lib/stats.js';
  import { formatNumber } from '../lib/format.js';
  import { fieldLabel, fieldTooltip, sortFieldKeys } from '../lib/fields.js';
  import FieldBar from './widgets/FieldBar.svelte';
  import ScatterplotMatrix from './stats/ScatterplotMatrix.svelte';
  import WordFrequency from './stats/WordFrequency.svelte';
  import DataSourceSelector from './stats/DataSourceSelector.svelte';

  // --- Data source ---
  function getSourceItems(source, results, selected) {
    if (source === 'results') return results;
    if (source === 'selection') return results.filter(r => selected.has(r.video_name));
    if (source === 'dataset') return results;
    return [];
  }

  $: sourceAItems = getSourceItems($statsSourceA, $currentResults, $selectedVideos);
  $: sourceBItems = $statsSourceB !== 'none' ? getSourceItems($statsSourceB, $currentResults, $selectedVideos) : null;

  $: fieldsA = $showStats ? collectNumericFields(sourceAItems) : {};
  $: fieldsB = $showStats && sourceBItems ? collectNumericFields(sourceBItems) : null;

  $: sortedKeys = sortFieldKeys(Object.keys(fieldsA));
  $: {
    if ($activeFields.size === 0 && sortedKeys.length > 0) $activeFields = new Set(sortedKeys);
  }

  function toggleField(key) {
    const s = new Set($activeFields);
    if (s.has(key)) s.delete(key); else s.add(key);
    $activeFields = s;
  }

  $: splomFieldsA = sortedKeys
    .filter(key => $activeFields.has(key) && fieldsA[key])
    .map(key => ({ key, values: fieldsA[key] }));
  $: splomFieldsB = fieldsB
    ? sortedKeys.filter(key => $activeFields.has(key) && fieldsB[key]).map(key => ({ key, values: fieldsB[key] }))
    : null;

  function fmt(v) { return formatNumber(v); }
  function summaryValue(key) {
    const sA = summarize(fieldsA[key] || []);
    if (fieldsB && fieldsB[key]) {
      const sB = summarize(fieldsB[key]);
      const diff = sA.mean - sB.mean;
      return `${diff >= 0 ? '+' : ''}${fmt(diff)} (Δ)`;
    }
    return `${fmt(sA.mean)} (${fmt(sA.min)}..${fmt(sA.max)})`;
  }

  // --- Vertical resize (panel height) ---
  let vDragging = false;
  let vStartY = 0;
  let vStartH = 0;

  function startVResize(e) {
    vDragging = true; vStartY = e.clientY; vStartH = $statsHeight;
    document.body.style.cursor = 'ns-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  }

  // --- Horizontal column splits (null = use flex 1/3 default) ---
  let col1W = null;
  let col3W = null;
  let hDrag = 0;     // 0=none, 1=left split, 2=right split
  let hStartX = 0;
  let hStartW = 0;

  let fieldsEl;
  let wordsEl;

  function startSplit(which, e) {
    hDrag = which; hStartX = e.clientX;
    if (which === 1) {
      if (col1W === null && fieldsEl) col1W = fieldsEl.getBoundingClientRect().width;
      hStartW = col1W || 0;
    } else {
      if (col3W === null && wordsEl) col3W = wordsEl.getBoundingClientRect().width;
      hStartW = col3W || 0;
    }
    document.body.style.cursor = 'ew-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  }

  function onMouseMove(e) {
    if (vDragging) {
      $statsHeight = Math.max(40, vStartH + e.clientY - vStartY);
    }
    if (hDrag === 1) {
      col1W = Math.max(40, hStartW + e.clientX - hStartX);
    } else if (hDrag === 2) {
      col3W = Math.max(40, hStartW - (e.clientX - hStartX));
    }
  }

  function onMouseUp() {
    if (vDragging || hDrag) {
      vDragging = false; hDrag = 0;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    }
  }
</script>

<svelte:window on:mousemove={onMouseMove} on:mouseup={onMouseUp} />

{#if $showStats}
  <div class="stats-panel" style="height: {$statsHeight}px;">
    <div class="stats-header separator dotted">
      <div class="section-label">Data Source</div>
      <DataSourceSelector />
    </div>

    <div class="stats-body">
      <!-- Left: Fields -->
      <div class="col fields-col" bind:this={fieldsEl}
           style={col1W !== null ? `width: ${col1W}px; flex: none;` : ''}>
        <div class="section-label">Fields</div>
        <div class="field-list">
          {#each sortedKeys as key}
            <FieldBar label={fieldLabel(key)} value={summaryValue(key)}
                      tooltip={fieldTooltip(key)}
                      toggleable={true} active={$activeFields.has(key)}
                      on:click={() => toggleField(key)} />
          {/each}
          {#if sortedKeys.length === 0}
            <FieldBar label="Stats" value="No numeric data" />
          {/if}
        </div>
      </div>

      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div class="split-handle" on:mousedown={(e) => startSplit(1, e)} title="Drag to resize"></div>

      <!-- Center: Scatterplot Matrix -->
      <div class="col splom-col">
        <div class="section-label">Scatterplot Matrix</div>
        <ScatterplotMatrix fields={splomFieldsA} fieldsB={splomFieldsB} />
      </div>

      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div class="split-handle" on:mousedown={(e) => startSplit(2, e)} title="Drag to resize"></div>

      <!-- Right: Words -->
      <div class="col words-col" bind:this={wordsEl}
           style={col3W !== null ? `width: ${col3W}px; flex: none;` : ''}>
        <div class="section-label">Word Frequency</div>
        <WordFrequency itemsA={sourceAItems} itemsB={sourceBItems} />
      </div>
    </div>
  </div>
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="v-resize-handle" class:active={vDragging} on:mousedown={startVResize}
       title="Drag to resize statistics panel"></div>
{/if}

<style>
  .stats-panel {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    display: flex; flex-direction: column;
    overflow: hidden; flex-shrink: 0;
  }
  .stats-header {
    display: flex; gap: var(--space-xl); align-items: flex-start;
    padding: var(--space-sm) var(--space-2xl);
    flex-shrink: 0;
  }
  .stats-body {
    flex: 1; min-height: 0;
    display: flex;
    padding: 0 var(--space-md) var(--space-sm);
  }
  .col { min-height: 0; overflow: hidden; }
  .fields-col {
    flex: 1; min-width: 0;
    overflow-y: auto; display: flex; flex-direction: column; gap: var(--space-xs);
    padding: 0 var(--space-sm);
  }
  .section-label {
    font-size: var(--font-size-xxs); text-transform: uppercase;
    letter-spacing: 0.5px; color: var(--accent); flex-shrink: 0;
  }
  .field-list {
    display: flex; flex-direction: column; gap: var(--space-xs);
  }
  .splom-col {
    flex: 1; min-width: 0;
    display: flex; flex-direction: column;
    padding: 0 var(--space-sm);
  }
  .words-col {
    flex: 1; min-width: 0;
    display: flex; flex-direction: column;
    padding: 0 var(--space-sm);
  }
  .split-handle {
    width: var(--resize-handle-size); flex-shrink: 0;
    cursor: ew-resize; background: transparent;
    transition: background 0.15s;
    border-left: 1px solid var(--border);
  }
  .split-handle:hover { background: var(--accent); }
  .v-resize-handle {
    height: var(--resize-handle-size); cursor: ns-resize;
    background: transparent; transition: background 0.15s; flex-shrink: 0;
    border-bottom: 1px solid var(--border);
  }
  .v-resize-handle:hover, .v-resize-handle.active { background: var(--accent); }
</style>
