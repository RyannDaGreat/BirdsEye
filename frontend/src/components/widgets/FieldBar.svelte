<!--
  Field bar: a small chip showing a field label + value.
  Label is dim, value is accent. Used in stats panel, detail panel, anywhere fields appear.
  Optionally wraps in a Popover for tooltip on hover.
  When toggleable=true, clicking toggles the active state (for scatterplot matrix field selection).
-->
<script>
  import Popover from './Popover.svelte';

  export let label = '';
  export let value = '';
  export let tooltip = '';  // HTML tooltip text (empty = no popover)
  export let hasDesc = false;  // true if tooltip exists (for cursor styling)
  export let toggleable = false;  // true in stats panel for scatterplot matrix field selection
  export let active = false;  // whether this field is toggled on
</script>

{#if tooltip}
  <Popover text={tooltip}>
    <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
    <span slot="trigger" class="field-bar" class:has-desc={hasDesc || !!tooltip}
          class:toggleable class:active on:click>
      <span class="field-label">{label}:</span>
      <span class="field-value">{value}</span>
    </span>
  </Popover>
{:else}
  <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
  <span class="field-bar" class:toggleable class:active on:click>
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
  .toggleable { cursor: pointer; transition: border-color 0.15s; }
  .toggleable:hover { border-color: var(--text-dim); }
  .active { border-color: var(--accent); }
</style>
