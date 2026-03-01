<script>
  import { showStats, currentResults, selectedVideos } from '../lib/stores.js';
  import { collectNumericFields, summarize } from '../lib/stats.js';
  import { formatNumber } from '../lib/format.js';
  import { fieldLabel } from '../lib/fields.js';
  import FieldBar from './widgets/FieldBar.svelte';

  $: resultsFields = $showStats ? collectNumericFields($currentResults) : {};
  $: selectedItems = $showStats ? $currentResults.filter(r => $selectedVideos.has(r.video_name)) : [];
  $: selectedFields = $showStats && selectedItems.length > 0 ? collectNumericFields(selectedItems) : {};
  $: hasSelected = $selectedVideos.size > 0;

  function fmt(v) { return formatNumber(v); }
</script>

<div class="panel" class:visible={$showStats}>
  <div class="stats-section">
    <div class="section-title">Current Results ({$currentResults.length})</div>
    <div class="stats-row">
      {#each Object.entries(resultsFields) as [key, vals]}
        {@const s = summarize(vals)}
        <FieldBar label={fieldLabel(key)} value="{fmt(s.mean)} ({fmt(s.min)}..{fmt(s.max)})" />
      {/each}
      {#if Object.keys(resultsFields).length === 0}
        <FieldBar label="Stats" value="No numeric data available" />
      {/if}
    </div>
  </div>
  {#if hasSelected}
    <div class="stats-section">
      <div class="section-title">Selected ({$selectedVideos.size})</div>
      <div class="stats-row">
        {#each Object.entries(selectedFields) as [key, vals]}
          {@const s = summarize(vals)}
          <FieldBar label={fieldLabel(key)} value="{fmt(s.mean)} ({fmt(s.min)}..{fmt(s.max)})" />
        {/each}
      </div>
    </div>
  {/if}
</div>

<style>
  .stats-section { display: flex; flex-direction: column; gap: var(--space-sm); min-width: 200px; }
  .section-title { font-size: var(--font-size-xs); text-transform: uppercase; letter-spacing: 0.5px; color: var(--accent); margin-bottom: var(--space-xs); }
  .stats-row { display: flex; gap: var(--space-sm); flex-wrap: wrap; }
</style>
