<!--
  Scatterplot Matrix (SPLOM): N×N grid of pairwise scatter plots.
  Diagonal cells: histogram per field. Off-diagonal: scatter plots.
  Canvas-rendered at native DPI for crisp output. Always square cells.
  Labels outside the grid (top header + left column). Hover shows correlation.
-->
<script>
  import { tick } from 'svelte';
  import { setupCanvas, drawScatter, drawHistogram } from '../../lib/canvas.js';
  import { pearsonCorrelation } from '../../lib/stats.js';
  import { fieldLabel } from '../../lib/fields.js';

  export let fields = [];     // [{key, values: number[]}]
  export let fieldsB = null;  // same shape, or null

  let canvases = {};
  let containerEl;
  let hoverInfo = '';
  let hoverX = 0;
  let hoverY = 0;

  $: n = fields.length;

  function cellKey(row, col) { return `${row}_${col}`; }

  async function renderAll() {
    await tick();
    if (!containerEl || n === 0) return;

    for (let row = 0; row < n; row++) {
      for (let col = 0; col < n; col++) {
        const canvas = canvases[cellKey(row, col)];
        if (!canvas) continue;
        const { ctx, w, h } = setupCanvas(canvas);
        if (w <= 0 || h <= 0) continue;
        ctx.clearRect(0, 0, w, h);

        if (row === col) {
          if (fieldsB) drawHistogram(ctx, fieldsB[row].values, 20, w, h, '#ff6b35');
          drawHistogram(ctx, fields[row].values, 20, w, h, '#4a9eff');
        } else {
          if (fieldsB) {
            drawScatter(ctx, fieldsB[col].values, fieldsB[row].values, w, h, '#ff6b35', 0.2);
          }
          drawScatter(ctx, fields[col].values, fields[row].values, w, h, '#4a9eff', 0.3);
        }
      }
    }
  }

  $: if (fields && n > 0) renderAll();

  function onCellHover(e, row, col) {
    if (row === col) {
      const vals = fields[row].values;
      hoverInfo = `${fieldLabel(fields[row].key)}: ${vals.length} samples`;
    } else {
      const r = pearsonCorrelation(fields[col].values, fields[row].values);
      hoverInfo = `${fieldLabel(fields[col].key)} × ${fieldLabel(fields[row].key)}: r = ${r.toFixed(3)}`;
    }
    const rect = containerEl.getBoundingClientRect();
    hoverX = e.clientX - rect.left + 12;
    hoverY = e.clientY - rect.top - 8;
  }

  function onCellLeave() { hoverInfo = ''; }
</script>

{#if n > 0}
  <div class="splom-outer" bind:this={containerEl}>
    <!-- Column headers (top) -->
    <div class="splom-header-row" style="grid-template-columns: var(--label-w) repeat({n}, 1fr);">
      <div class="corner"></div>
      {#each fields as f}
        <div class="col-label" title={fieldLabel(f.key)}>{fieldLabel(f.key)}</div>
      {/each}
    </div>
    <!-- Grid rows: row label + N cells -->
    <div class="splom-body" style="grid-template-columns: var(--label-w) repeat({n}, 1fr); grid-template-rows: repeat({n}, 1fr);">
      {#each { length: n } as _, row}
        <div class="row-label" title={fieldLabel(fields[row].key)}>{fieldLabel(fields[row].key)}</div>
        {#each { length: n } as _, col}
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div class="splom-cell"
               on:mousemove={(e) => onCellHover(e, row, col)}
               on:mouseleave={onCellLeave}>
            <canvas bind:this={canvases[cellKey(row, col)]}></canvas>
          </div>
        {/each}
      {/each}
    </div>
    <!-- Hover tooltip -->
    {#if hoverInfo}
      <div class="splom-tip" style="left: {hoverX}px; top: {hoverY}px;">{hoverInfo}</div>
    {/if}
  </div>
{:else}
  <div class="splom-empty">Toggle fields in Summary view to show the scatterplot matrix.</div>
{/if}

<style>
  .splom-outer {
    --label-w: 60px;
    position: relative; display: flex; flex-direction: column;
    height: 100%; overflow: hidden;
  }
  .splom-header-row {
    display: grid; flex-shrink: 0;
  }
  .corner { }
  .col-label {
    font-size: var(--font-size-xxs); color: var(--text-dim);
    text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    padding: var(--space-xs) 0;
  }
  .splom-body {
    display: grid; flex: 1; gap: 1px; background: var(--border);
    min-height: 0;
  }
  .row-label {
    font-size: var(--font-size-xxs); color: var(--text-dim);
    display: flex; align-items: center; justify-content: flex-end;
    padding-right: var(--space-sm);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    background: var(--surface);
  }
  .splom-cell {
    background: var(--bg); overflow: hidden; aspect-ratio: 1;
  }
  .splom-cell canvas { display: block; width: 100%; height: 100%; }
  .splom-tip {
    position: absolute; pointer-events: none; z-index: 10;
    background: var(--surface2); border: 1px solid var(--border);
    color: var(--text); padding: var(--space-xs) var(--space-sm);
    border-radius: var(--radius-xs); font-size: var(--font-size-xs);
    white-space: nowrap;
  }
  .splom-empty {
    display: flex; align-items: center; justify-content: center;
    height: 100%; color: var(--text-dim); font-size: var(--font-size-control);
  }
</style>
