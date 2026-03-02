<!--
  Two-row data source selector for the statistics panel.
  Top row (mandatory): Results | Dataset | Selection
  Bottom row (optional): Results | Dataset | Selection | None
  When bottom != None, stats show differential (top - bottom).
-->
<script>
  import { statsSourceA, statsSourceB, selectedVideos } from '../../lib/stores.js';
  import ModeTabRow from '../widgets/ModeTabRow.svelte';
  import Popover from '../widgets/Popover.svelte';

  const sourceOptions = [
    { value: 'results', label: 'Results' },
    { value: 'dataset', label: 'Dataset' },
    { value: 'selection', label: 'Selection' },
  ];

  const minusOptions = [
    { value: 'results', label: 'Results' },
    { value: 'dataset', label: 'Dataset' },
    { value: 'selection', label: 'Selection' },
    { value: 'none', label: 'None' },
  ];

  $: disabledSet = $selectedVideos.size === 0 ? new Set(['selection']) : new Set();
</script>

<div class="source-selector">
  <ModeTabRow options={sourceOptions} bind:value={$statsSourceA} disabled={disabledSet} />
  <div class="minus-row">
    <span class="minus-label">−</span>
    <ModeTabRow options={minusOptions} bind:value={$statsSourceB} disabled={disabledSet} />
    <Popover text="<strong>Data Source</strong><br/>Top row: primary population for statistics.<br/>Bottom row: optional comparison. When set, statistics show the difference (primary minus comparison).<br/><br/>Example: <em>Results − Dataset</em> reveals which values are over- or under-represented in your search results compared to the full dataset.">
      <button slot="trigger" class="help-icon" title="What does this do?">
        <iconify-icon icon="mdi:help-circle-outline" inline></iconify-icon>
      </button>
    </Popover>
  </div>
</div>

<style>
  .source-selector { display: flex; flex-direction: column; gap: var(--space-xs); }
  .minus-row { display: flex; align-items: center; gap: var(--space-sm); }
  .minus-label { color: var(--text-dim); font-size: var(--font-size-base); font-weight: 600; width: var(--space-xl); text-align: center; }
  .help-icon {
    background: none; border: none; color: var(--text-dim); cursor: pointer;
    font-size: var(--font-size-base); padding: 0; line-height: 1;
  }
  .help-icon:hover { color: var(--accent); }
</style>
