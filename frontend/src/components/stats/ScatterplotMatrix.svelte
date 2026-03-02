<!--
  Scatterplot Matrix (SPLOM): N×N grid of pairwise scatter plots.
  Diagonal cells: histogram per field. Off-diagonal: scatter plots.
  Canvas-rendered for performance with thousands of data points.
-->
<script>
  import { onMount, afterUpdate, tick } from 'svelte';
  import { drawScatter, drawHistogram } from '../../lib/canvas.js';

  export let fields = [];     // [{key, values: number[]}] — active fields with their data
  export let fieldsB = null;  // same shape, or null — comparison data for differential

  let canvases = {};
  let containerEl;

  $: n = fields.length;
  $: gridStyle = `grid-template-columns: repeat(${n}, 1fr); grid-template-rows: repeat(${n}, 1fr);`;

  function cellKey(row, col) { return `${row}_${col}`; }

  async function renderAll() {
    await tick();
    if (!containerEl || n === 0) return;

    for (let row = 0; row < n; row++) {
      for (let col = 0; col < n; col++) {
        const canvas = canvases[cellKey(row, col)];
        if (!canvas) continue;
        const rect = canvas.parentElement.getBoundingClientRect();
        const w = Math.floor(rect.width);
        const h = Math.floor(rect.height);
        if (w <= 0 || h <= 0) continue;
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, w, h);

        if (row === col) {
          // Diagonal: histogram
          if (fieldsB) drawHistogram(ctx, fieldsB[row].values, 20, w, h, '#ff6b35');
          drawHistogram(ctx, fields[row].values, 20, w, h, '#4a9eff');
        } else {
          // Off-diagonal: scatter
          const xVals = fields[col].values;
          const yVals = fields[row].values;
          if (fieldsB) {
            drawScatter(ctx, fieldsB[col].values, fieldsB[row].values, w, h, '#ff6b35', 0.2);
          }
          drawScatter(ctx, xVals, yVals, w, h, '#4a9eff', 0.3);
        }
      }
    }
  }

  $: if (fields && n > 0) renderAll();

  onMount(() => { renderAll(); });
</script>

{#if n > 0}
  <div class="splom-grid" style={gridStyle} bind:this={containerEl}>
    {#each { length: n } as _, row}
      {#each { length: n } as _, col}
        <div class="splom-cell">
          {#if row === n - 1}
            <span class="axis-label bottom">{fields[col].key}</span>
          {/if}
          {#if col === 0}
            <span class="axis-label left">{fields[row].key}</span>
          {/if}
          <canvas bind:this={canvases[cellKey(row, col)]}></canvas>
        </div>
      {/each}
    {/each}
  </div>
{:else}
  <div class="splom-empty">Toggle fields in Summary view to show the scatterplot matrix.</div>
{/if}

<style>
  .splom-grid {
    display: grid; width: 100%; height: 100%; gap: 1px;
    background: var(--border);
  }
  .splom-cell {
    position: relative; background: var(--bg); overflow: hidden;
  }
  .splom-cell canvas { display: block; width: 100%; height: 100%; }
  .axis-label {
    position: absolute; font-size: var(--font-size-xxs); color: var(--text-dim);
    pointer-events: none; z-index: 1;
  }
  .axis-label.bottom { bottom: 1px; left: 50%; transform: translateX(-50%); }
  .axis-label.left { top: 50%; left: 1px; transform: translateY(-50%) rotate(-90deg); transform-origin: left center; }
  .splom-empty {
    display: flex; align-items: center; justify-content: center;
    height: 100%; color: var(--text-dim); font-size: var(--font-size-control);
  }
</style>
