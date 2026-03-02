<!--
  Collapsible accordion wrapper for preview sections.
  Wraps any content in a labeled, expandable/collapsible container.
-->
<script>
  export let label = '';
  export let defaultOpen = true;
  export let tooltip = '';

  let open = defaultOpen;
</script>

<div class="preview-section">
  <button class="section-header" on:click={() => open = !open} title={tooltip}>
    <iconify-icon icon={open ? 'mdi:chevron-down' : 'mdi:chevron-right'} inline></iconify-icon>
    {label}
  </button>
  {#if open}
    <div class="section-body">
      <slot />
    </div>
  {/if}
</div>

<style>
  .preview-section { margin-bottom: var(--space-sm); }
  .section-header {
    display: flex; align-items: center; gap: var(--space-xs);
    background: none; border: none; cursor: pointer;
    font-family: var(--font); font-size: var(--font-size-xs);
    color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.5px;
    padding: var(--space-xs) 0; width: 100%;
  }
  .section-header:hover { color: var(--accent); }
  .section-body { padding-top: var(--space-xs); }
</style>
