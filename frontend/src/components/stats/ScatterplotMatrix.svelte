<!--
  Scatterplot Matrix (SPLOM): N×N grid of pairwise scatter plots.
  Diagonal: histogram. Off-diagonal: scatter. Always square cells.
  Cell size computed from container dimensions. Dividing lines between cells.
  Labels outside grid. Hover shows Pearson correlation.
-->
<script>
  import { onMount, onDestroy, tick } from 'svelte';
  import { setupCanvas, drawScatter, drawHistogram } from '../../lib/canvas.js';
  import { pearsonCorrelation } from '../../lib/stats.js';
  import { fieldLabel } from '../../lib/fields.js';

  export let fields = [];
  export let fieldsB = null;

  let canvases = {};
  let outerEl;
  let cellSize = 0;
  let hoverInfo = '';
  let hoverX = 0;
  let hoverY = 0;
  let observer;

  const LABEL_W = 60;
  const HEADER_H = 18;
  const GAP = 1;

  $: n = fields.length;

  function cellKey(r, c) { return `${r}_${c}`; }

  function computeLayout() {
    if (!outerEl || n === 0) { cellSize = 0; return; }
    const rect = outerEl.getBoundingClientRect();
    const availW = rect.width - LABEL_W - GAP * (n - 1);
    const availH = rect.height - HEADER_H - GAP * (n - 1);
    cellSize = Math.max(20, Math.floor(Math.min(availW / n, availH / n)));
  }

  async function renderAll() {
    computeLayout();
    await tick();
    if (cellSize <= 0 || n === 0) return;

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

  onMount(() => {
    observer = new ResizeObserver(() => renderAll());
    if (outerEl) observer.observe(outerEl);
  });
  onDestroy(() => { if (observer) observer.disconnect(); });

  function onCellHover(e, row, col) {
    if (row === col) {
      hoverInfo = `${fieldLabel(fields[row].key)}: ${fields[row].values.length} samples`;
    } else {
      const r = pearsonCorrelation(fields[col].values, fields[row].values);
      hoverInfo = `${fieldLabel(fields[col].key)} × ${fieldLabel(fields[row].key)}: r = ${r.toFixed(3)}`;
    }
    const rect = outerEl.getBoundingClientRect();
    hoverX = e.clientX - rect.left + 12;
    hoverY = e.clientY - rect.top - 8;
  }

  function onCellLeave() { hoverInfo = ''; }

  $: gridW = n > 0 ? LABEL_W + n * cellSize + (n - 1) * GAP : 0;
  $: gridH = n > 0 ? HEADER_H + n * cellSize + (n - 1) * GAP : 0;
</script>

{#if n > 0 && cellSize > 0}
  <div class="splom-outer" bind:this={outerEl}>
    <div class="splom-frame" style="width: {gridW}px; height: {gridH}px;">
      <!-- Column headers -->
      <div class="header-row" style="left: {LABEL_W}px; height: {HEADER_H}px;">
        {#each fields as f, i}
          <span class="col-label" style="left: {i * (cellSize + GAP)}px; width: {cellSize}px;"
                title={fieldLabel(f.key)}>{fieldLabel(f.key)}</span>
        {/each}
      </div>
      <!-- Row labels -->
      {#each fields as f, i}
        <span class="row-label" style="top: {HEADER_H + i * (cellSize + GAP)}px; width: {LABEL_W}px; height: {cellSize}px;"
              title={fieldLabel(f.key)}>{fieldLabel(f.key)}</span>
      {/each}
      <!-- Cells -->
      {#each { length: n } as _, row}
        {#each { length: n } as _, col}
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div class="splom-cell"
               style="left: {LABEL_W + col * (cellSize + GAP)}px; top: {HEADER_H + row * (cellSize + GAP)}px; width: {cellSize}px; height: {cellSize}px;"
               on:mousemove={(e) => onCellHover(e, row, col)}
               on:mouseleave={onCellLeave}>
            <canvas bind:this={canvases[cellKey(row, col)]}></canvas>
          </div>
        {/each}
      {/each}
    </div>
    {#if hoverInfo}
      <div class="splom-tip" style="left: {hoverX}px; top: {hoverY}px;">{hoverInfo}</div>
    {/if}
  </div>
{:else}
  <div class="splom-empty" bind:this={outerEl}>Toggle fields in Summary view to show the scatterplot matrix.</div>
{/if}

<style>
  .splom-outer {
    position: relative; width: 100%; height: 100%; overflow: hidden;
    display: flex; align-items: flex-start; justify-content: center;
  }
  .splom-frame {
    position: relative; flex-shrink: 0;
  }
  .header-row {
    position: absolute; top: 0;
  }
  .col-label {
    position: absolute; top: 0;
    font-size: var(--font-size-xxs); color: var(--text-dim);
    text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    line-height: 18px;
  }
  .row-label {
    position: absolute; left: 0;
    font-size: var(--font-size-xxs); color: var(--text-dim);
    display: flex; align-items: center; justify-content: flex-end;
    padding-right: var(--space-sm); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .splom-cell {
    position: absolute;
    background: var(--bg); border: 1px solid var(--border);
    overflow: hidden;
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
    width: 100%; height: 100%; color: var(--text-dim); font-size: var(--font-size-control);
  }
</style>
