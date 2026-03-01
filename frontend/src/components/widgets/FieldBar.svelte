<!--
  Field bar: a small chip showing a field label + value.
  Label is dim, value is accent. Used in stats panel, detail panel, anywhere fields appear.
  Optionally wraps in a Popover for tooltip on hover.
-->
<script>
  import Popover from './Popover.svelte';

  export let label = '';
  export let value = '';
  export let tooltip = '';  // HTML tooltip text (empty = no popover)
  export let hasDesc = false;  // true if tooltip exists (for cursor styling)
</script>

{#if tooltip}
  <Popover text={tooltip}>
    <span slot="trigger" class="field-bar" class:has-desc={hasDesc || !!tooltip}>
      <span class="field-label">{label}:</span>
      <span class="field-value">{value}</span>
    </span>
  </Popover>
{:else}
  <span class="field-bar">
    <span class="field-label">{label}:</span>
    <span class="field-value">{value}</span>
  </span>
{/if}

<style>
  .field-bar {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: var(--space-xs) var(--space-sm);
    font-size: var(--font-size-xs);
    white-space: nowrap;
    display: inline-flex;
    gap: var(--space-xs);
  }
  .field-label { color: var(--text-dim); }
  .field-value { color: var(--accent); }
  .has-desc { cursor: help; }
</style>
