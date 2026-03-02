<!--
  Statistics panel: all three views side by side.
  Left: Summary (vertical field bar list). Center: Scatterplot Matrix. Right: Words.
-->
<script>
  import { showStats, currentResults, selectedVideos, statsSourceA, statsSourceB, activeFields, statsHeight } from '../lib/stores.js';
  import { collectNumericFields, summarize } from '../lib/stats.js';
  import { formatNumber } from '../lib/format.js';
  import { fieldLabel, fieldTooltip } from '../lib/fields.js';
  import FieldBar from './widgets/FieldBar.svelte';
  import ScatterplotMatrix from './stats/ScatterplotMatrix.svelte';
  import WordFrequency from './stats/WordFrequency.svelte';
  import DataSourceSelector from './stats/DataSourceSelector.svelte';

  // --- Data source computation ---
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

  // Active fields init
  $: {
    const keys = Object.keys(fieldsA);
    if ($activeFields.size === 0 && keys.length > 0) {
      $activeFields = new Set(keys);
    }
  }

  function toggleField(key) {
    const s = new Set($activeFields);
    if (s.has(key)) s.delete(key); else s.add(key);
    $activeFields = s;
  }

  // SPLOM data
  $: splomFieldsA = Object.entries(fieldsA)
    .filter(([key]) => $activeFields.has(key))
    .map(([key, values]) => ({ key, values }));
  $: splomFieldsB = fieldsB
    ? Object.entries(fieldsB)
        .filter(([key]) => $activeFields.has(key))
        .map(([key, values]) => ({ key, values }))
    : null;

  function fmt(v) { return formatNumber(v); }

  function summaryValue(key) {
    const sA = summarize(fieldsA[key] || []);
    if (fieldsB && fieldsB[key]) {
      const sB = summarize(fieldsB[key]);
      const diff = sA.mean - sB.mean;
      const sign = diff >= 0 ? '+' : '';
      return `${sign}${fmt(diff)} (Δ)`;
    }
    return `${fmt(sA.mean)} (${fmt(sA.min)}..${fmt(sA.max)})`;
  }

  // Resize
  let dragging = false;
  let startY = 0;
  let startHeight = 0;

  function startResize(e) {
    dragging = true;
    startY = e.clientY;
    startHeight = $statsHeight;
    document.body.style.cursor = 'ns-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  }

  function onMouseMove(e) {
    if (!dragging) return;
    const maxH = window.innerHeight * 0.6;
    $statsHeight = Math.max(100, Math.min(maxH, startHeight + e.clientY - startY));
  }

  function onMouseUp() {
    if (!dragging) return;
    dragging = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  }
</script>

<svelte:window on:mousemove={onMouseMove} on:mouseup={onMouseUp} />

{#if $showStats}
  <div class="stats-panel" style="height: {$statsHeight}px;">
    <div class="stats-header">
      <DataSourceSelector />
    </div>

    <div class="stats-body">
      <!-- Left: Summary (vertical list of field bars) -->
      <div class="summary-col">
        <div class="section-label">Fields</div>
        <div class="field-list">
          {#each Object.entries(fieldsA) as [key, vals]}
            <FieldBar label={fieldLabel(key)} value={summaryValue(key)}
                      tooltip={fieldTooltip(key)}
                      toggleable={true} active={$activeFields.has(key)}
                      on:click={() => toggleField(key)} />
          {/each}
          {#if Object.keys(fieldsA).length === 0}
            <FieldBar label="Stats" value="No numeric data" />
          {/if}
        </div>
      </div>

      <!-- Center: Scatterplot Matrix -->
      <div class="splom-col">
        <ScatterplotMatrix fields={splomFieldsA} fieldsB={splomFieldsB} />
      </div>

      <!-- Right: Word Frequency -->
      <div class="words-col">
        <WordFrequency itemsA={sourceAItems} itemsB={sourceBItems} />
      </div>
    </div>
  </div>
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="stats-resize-handle resize-handle" class:dragging on:mousedown={startResize}
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
    display: flex; gap: var(--space-md);
    padding: 0 var(--space-2xl) var(--space-sm);
  }
  .summary-col {
    width: 180px; flex-shrink: 0;
    overflow-y: auto; display: flex; flex-direction: column; gap: var(--space-xs);
  }
  .section-label {
    font-size: var(--font-size-xxs); text-transform: uppercase;
    letter-spacing: 0.5px; color: var(--accent); flex-shrink: 0;
  }
  .field-list {
    display: flex; flex-direction: column; gap: var(--space-xs);
  }
  .splom-col {
    flex: 1; min-width: 0; min-height: 0;
  }
  .words-col {
    flex: 1; min-width: 0; min-height: 0;
    overflow-x: auto;
  }
  .stats-resize-handle {
    height: var(--resize-handle-size); cursor: ns-resize;
    background: transparent; transition: background 0.15s; flex-shrink: 0;
    border-bottom: 1px solid var(--border);
  }
  .stats-resize-handle:hover, .stats-resize-handle.dragging { background: var(--accent); }
</style>
