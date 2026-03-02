<!--
  Statistics panel with view tabs, data source selector, and resizable height.
  Views: Summary (field bars), Scatterplot Matrix, Words (word frequency).
-->
<script>
  import { showStats, currentResults, selectedVideos, statsView, statsSourceA, statsSourceB, activeFields, statsHeight } from '../lib/stores.js';
  import { collectNumericFields, summarize } from '../lib/stats.js';
  import { formatNumber } from '../lib/format.js';
  import { fieldLabel, fieldTooltip } from '../lib/fields.js';
  import FieldBar from './widgets/FieldBar.svelte';
  import ScatterplotMatrix from './stats/ScatterplotMatrix.svelte';
  import WordFrequency from './stats/WordFrequency.svelte';
  import ModeTabRow from './widgets/ModeTabRow.svelte';
  import DataSourceSelector from './stats/DataSourceSelector.svelte';

  const viewOptions = [
    { value: 'summary', label: 'Summary' },
    { value: 'scatterplot', label: 'Scatterplot Matrix' },
    { value: 'words', label: 'Words' },
  ];

  // --- Data source computation ---
  $: sourceAItems = getSourceItems($statsSourceA);
  $: sourceBItems = $statsSourceB !== 'none' ? getSourceItems($statsSourceB) : null;

  function getSourceItems(source) {
    if (source === 'results') return $currentResults;
    if (source === 'selection') return $currentResults.filter(r => $selectedVideos.has(r.video_name));
    if (source === 'dataset') return $currentResults; // TODO: fetch full dataset stats
    return [];
  }

  // --- Summary view data ---
  $: fieldsA = $showStats ? collectNumericFields(sourceAItems) : {};
  $: fieldsB = $showStats && sourceBItems ? collectNumericFields(sourceBItems) : null;

  // --- Active fields initialization ---
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

  // --- Scatterplot Matrix data ---
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

  // --- Resize ---
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
    const newH = Math.max(100, Math.min(maxH, startHeight + e.clientY - startY));
    $statsHeight = newH;
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
      <ModeTabRow options={viewOptions} bind:value={$statsView} />
      <DataSourceSelector />
    </div>

    <div class="stats-body">
      {#if $statsView === 'summary'}
        <div class="stats-row">
          {#each Object.entries(fieldsA) as [key, vals]}
            <FieldBar label={fieldLabel(key)} value={summaryValue(key)}
                      tooltip={fieldTooltip(key)}
                      toggleable={true} active={$activeFields.has(key)}
                      on:click={() => toggleField(key)} />
          {/each}
          {#if Object.keys(fieldsA).length === 0}
            <FieldBar label="Stats" value="No numeric data available" />
          {/if}
        </div>
      {:else if $statsView === 'scatterplot'}
        <ScatterplotMatrix fields={splomFieldsA} fieldsB={splomFieldsB} />
      {:else if $statsView === 'words'}
        <WordFrequency itemsA={sourceAItems} itemsB={sourceBItems} />
      {/if}
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
    padding: var(--space-md) var(--space-2xl);
    flex-shrink: 0;
  }
  .stats-body {
    flex: 1; overflow-y: auto;
    padding: 0 var(--space-2xl) var(--space-md);
    font-size: var(--font-size-small); color: var(--text-dim);
  }
  .stats-row { display: flex; gap: var(--space-sm); flex-wrap: wrap; }
  .stats-resize-handle {
    height: var(--resize-handle-size); cursor: ns-resize;
    background: transparent; transition: background 0.15s; flex-shrink: 0;
    border-bottom: 1px solid var(--border);
  }
  .stats-resize-handle:hover, .stats-resize-handle.dragging { background: var(--accent); }
  .stats-resize-handle::after {
    content: ''; position: absolute; width: var(--space-md); height: var(--space-md);
    border-radius: 50%; background: var(--text-dim); opacity: 0.4;
    top: 50%; left: 50%; transform: translate(-50%, -50%); pointer-events: none;
  }
  .placeholder {
    display: flex; align-items: center; justify-content: center;
    height: 100%; color: var(--text-dim); font-size: var(--font-size-base);
  }
</style>
