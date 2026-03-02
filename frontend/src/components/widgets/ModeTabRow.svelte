<!--
  Reusable row of mode tabs. Mimics the fuzzy/clip/hull search mode selector.
  Uses shared .mode-tabs / .mode-tab CSS from app.css.
  Props:
    options: [{value, label}]
    value: currently selected value (bind:value)
    disabled: Set of values that should be grayed out
-->
<script>
  import { createEventDispatcher } from 'svelte';

  export let options = [];
  export let value = '';
  export let disabled = new Set();

  const dispatch = createEventDispatcher();

  function select(v) {
    if (disabled.has(v)) return;
    value = v;
    dispatch('change', v);
  }
</script>

<div class="mode-tabs">
  {#each options as opt}
    <button class="mode-tab" class:active={value === opt.value}
            disabled={disabled.has(opt.value)}
            title={opt.tooltip || opt.label}
            on:click={() => select(opt.value)}>{opt.label}</button>
  {/each}
</div>
