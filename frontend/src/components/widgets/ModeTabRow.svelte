<!--
  Reusable row of mode tabs. Mimics the fuzzy/clip/hull search mode selector.
  Uses shared .mode-tabs / .mode-tab CSS from app.css.
  compact=true uses field-bar-sized tabs (smaller font, less padding).
-->
<script>
  import { createEventDispatcher } from 'svelte';

  export let options = [];
  export let value = '';
  export let disabled = new Set();
  export let compact = false;

  const dispatch = createEventDispatcher();

  function select(v) {
    if (disabled.has(v)) return;
    value = v;
    dispatch('change', v);
  }
</script>

<div class="mode-tabs" class:compact>
  {#each options as opt}
    <button class="mode-tab" class:active={value === opt.value}
            disabled={disabled.has(opt.value)}
            title={opt.tooltip || opt.label}
            on:click={() => select(opt.value)}>{opt.label}</button>
  {/each}
</div>

<style>
  .mode-tabs.compact {
    height: auto;
    padding: 1px;
  }
  .compact .mode-tab {
    font-size: var(--font-size-xs);
    padding: var(--space-xs) var(--space-sm);
    line-height: 1.3;
  }
</style>
