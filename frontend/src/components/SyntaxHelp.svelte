<script>
  import { showHelp, currentSort, fieldInfo } from '../lib/stores.js';
  import { parseSortKey } from '../lib/format.js';
  import { fieldLabel, fieldDescription } from '../lib/fields.js';

  $: ({ key: sortKey } = parseSortKey($currentSort));
  $: sortLabel = sortKey ? fieldLabel(sortKey) : '';
  $: sortDesc = sortKey ? fieldDescription(sortKey) : '';
</script>

<div class="panel block-layout" class:visible={$showHelp}>
  {#if sortKey}
    <div class="sort-info">
      <strong>Sorted by: {sortLabel}</strong>
      {#if sortDesc}
        — {sortDesc}
      {/if}
    </div>
  {/if}
  <strong>FZF Extended Search Syntax</strong> (Fuzzy mode):
  <div class="examples">
    <span><code>cat dog</code> — both words must match</span>
    <span><code>cat|dog</code> — either word matches</span>
    <span><code>!rain</code> — exclude "rain"</span>
    <span><code>'blue sky'</code> — exact phrase</span>
  </div>
  <div style="margin-top: var(--space-sm);">
    <strong>CLIP mode</strong>: describe what you want to see (e.g. "sunset over ocean").
    <strong>Hull mode</strong>: select videos first, then search for similar ones.
  </div>
</div>

<style>
  .examples { display: flex; gap: var(--space-3xl); flex-wrap: wrap; margin-top: var(--space-sm); }
  .sort-info {
    margin-bottom: var(--space-md);
    color: var(--text);
  }
</style>
