<script>
  /**
   * Histogram with range selection.
   * Props: label, histogram ({lo, hi, counts[]}), min, max, step
   */
  import { createEventDispatcher } from 'svelte';
  import Popover from './Popover.svelte';

  export let label = '';
  export let histogram = null;  // {lo, hi, counts} — full dataset distribution
  export let min = '';
  export let max = '';
  export let step = 1;
  export let numBins = 60;
  export let description = '';
  export let useLog = true;
  export let indicatorValue = null; // value to show as vertical line indicator
  export let count = null; // number of samples that have this field
  export let highlighted = false; // cross-component hover highlight

  const dispatch = createEventDispatcher();
  const H = 36;
  let chartEl;
  let dragging = null;
  let tooltip = null;

  // Axis range from server (fixed)
  $: lo = histogram?.lo ?? 0;
  $: hi = histogram?.hi ?? 1;
  $: span = hi - lo || 1;

  // Always use server histogram (full dataset distribution)
  $: bins = histogram?.counts || new Array(numBins).fill(0);
  $: peak = Math.max(1, useLog ? Math.log1p(Math.max(...bins)) : Math.max(...bins));
  $: n = bins.length || 1;

  $: indicatorFrac = (indicatorValue !== null && indicatorValue !== undefined) ? clamp((Number(indicatorValue) - lo) / span) : null;

  $: minF = hasVal(min) ? clamp((Number(min) - lo) / span) : 0;
  $: maxF = hasVal(max) ? clamp((Number(max) - lo) / span) : 1;
  $: hasRange = hasVal(min) || hasVal(max);

  function hasVal(v) { return v !== '' && v !== undefined && v !== null; }
  function clamp(v) { return Math.max(0, Math.min(1, v)); }
  function round(v) {
    if (step >= 1) return Math.round(v);
    const decimals = Math.max(0, Math.ceil(-Math.log10(step)));
    return Number(v.toFixed(decimals));
  }

  function startDrag(e, which) {
    dragging = which;
    document.body.style.cursor = 'ew-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  }

  function onMove(e) {
    if (!dragging || !chartEl) return;
    const r = chartEl.getBoundingClientRect();
    const f = clamp((e.clientX - r.left) / r.width);
    const v = round(lo + f * span);
    if (dragging === 'min') {
      if (hasVal(max) && v > Number(max)) {
        // Swap: min handle crossed max — become the max handle
        min = max;
        max = v;
        dragging = 'max';
      } else {
        min = v;
      }
    } else {
      if (hasVal(min) && v < Number(min)) {
        // Swap: max handle crossed min — become the min handle
        max = min;
        min = v;
        dragging = 'min';
      } else {
        max = v;
      }
    }
  }

  function onUp() {
    if (!dragging) return;
    dragging = null;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    dispatch('change');
  }

  function onHover(e) {
    if (dragging || !chartEl) return;
    const r = chartEl.getBoundingClientRect();
    const x = e.clientX - r.left;
    const i = clamp(Math.floor((x / r.width) * n) / n) * n | 0;
    const idx = Math.min(i, n - 1);
    const c = bins[idx] || 0;
    // x-axis value at this bin's center
    const binVal = round(lo + (idx + 0.5) * span / n);
    tooltip = { x, text: `${binVal}, ${c}` };
  }

  function clear() { min = ''; max = ''; dispatch('change'); }
</script>

<svelte:window on:mousemove={onMove} on:mouseup={onUp} />

<div class="hf" class:inactive={!hasRange} class:highlighted>
  <div class="hf-row">
    <span class="hf-label-group">
      <span class="label-sm">
        {#if description}
          <Popover text={'<strong>' + label + '</strong><br/>' + description}>
            <span slot="trigger" class="hf-help"><iconify-icon icon="mdi:help-circle-outline" inline></iconify-icon></span>
          </Popover>
        {/if}
        {label}{#if count !== null}<span class="hf-count">({count})</span>{/if}
      </span>
    </span>
    <input class="input-sm" type="text" placeholder="min" title="Minimum {label} value" bind:value={min} on:change={() => dispatch('change')} />
    <input class="input-sm" type="text" placeholder="max" title="Maximum {label} value" bind:value={max} on:change={() => dispatch('change')} />
    <button class="clear-btn" class:dim={!hasRange} on:click={clear} title="Clear {label} filter">&times;</button>
  </div>
  {#if bins.length > 0}
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="hf-chart" bind:this={chartEl}
         on:mousemove={onHover} on:mouseleave={() => tooltip = null}>
      <div class="hf-bars">
        {#each bins as c, i}
          <div class="hf-bar"
               class:lit={((i+1)/n > minF) && (i/n < maxF)}
               style="height:{c > 0 ? ((useLog ? Math.log1p(c) : c)/peak)*H : 0}px; width:{100/n}%"></div>
        {/each}
        <div class="hf-sel" style="left:{minF*100}%; width:{(maxF-minF)*100}%"></div>
      </div>
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div class="hf-h" style="left:{minF*100}%" on:mousedown={e => startDrag(e,'min')}></div>
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div class="hf-h" style="left:{maxF*100}%" on:mousedown={e => startDrag(e,'max')}></div>
      {#if indicatorFrac !== null}
        <div class="hf-indicator" style="left:{indicatorFrac * 100}%"></div>
      {/if}
      {#if tooltip}
        <div class="hf-tip" style="left:{tooltip.x}px">{tooltip.text}</div>
      {/if}
    </div>
  {:else}
    <div class="hf-empty">not available</div>
  {/if}
</div>

<style>
  .hf { width: 100%; transition: opacity 0.15s; }
  .hf.inactive { opacity: 0.3; }
  .hf.inactive:hover { opacity: 0.7; }
  .hf.highlighted { opacity: 1 !important; }
  .hf.highlighted .hf-chart { outline: 1px solid var(--accent); }
  .hf-row {
    display: flex; align-items: center; gap: var(--space-sm);
    margin-bottom: var(--space-xs);
  }
  .hf-label-group { display: flex; align-items: center; gap: var(--space-xs); flex: 1; }
  .hf-row :global(.input-sm) { width: 40px; flex-shrink: 0; }
  .hf-row :global(.clear-btn) { flex-shrink: 0; }
  .hf-help { color: var(--text-dim); font-size: var(--font-size-xs); cursor: pointer; }
  .hf-help:hover { color: var(--accent); }
  .hf-count { color: var(--text-dim); font-size: var(--font-size-xxs); margin-left: var(--space-xs); }

  .hf-chart {
    position: relative; height: var(--chart-height);
    background: var(--bg); border-radius: var(--radius-xs); cursor: crosshair;
  }
  .hf-bars {
    position: absolute; inset: 0; display: flex;
    align-items: flex-end; overflow: hidden; border-radius: var(--radius-xs);
  }
  .hf-bar { background: var(--border); }
  .hf-bar.lit { background: var(--accent-dim); }
  .hf-sel {
    position: absolute; top: 0; bottom: 0;
    background: rgba(74,158,255,0.08); pointer-events: none; z-index: 1;
  }
  .hf-h {
    position: absolute; top: calc(var(--space-xs) * -1); bottom: calc(var(--space-xs) * -1);
    width: 6px; background: var(--accent); border-radius: var(--radius-xs);
    cursor: ew-resize; z-index: 3; transform: translateX(-3px);
  }
  .hf-h:hover { background: var(--text); }
  .hf-indicator {
    position: absolute; top: 0; bottom: 0; width: 1px;
    background: #fff; z-index: 4; pointer-events: none;
    border-left: 1px dashed rgba(255,255,255,0.8);
  }
  .hf-empty {
    height: var(--chart-height); background: var(--bg); border-radius: var(--radius-xs);
    display: flex; align-items: center; justify-content: center;
    font-size: var(--font-size-xxs); color: var(--border); text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .hf-tip {
    position: absolute; top: calc(var(--chart-height) + var(--space-xs));
    background: var(--surface2); border: 1px solid var(--border);
    color: var(--text); padding: 1px var(--space-sm); border-radius: var(--radius-xs);
    font-size: var(--font-size-xxs); pointer-events: none; transform: translateX(-50%); z-index: 10;
  }
</style>
