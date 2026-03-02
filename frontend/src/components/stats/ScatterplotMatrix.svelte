<!--
  Scatterplot Matrix (SPLOM): N×N grid of pairwise scatter plots.
  Diagonal: histogram. Off-diagonal: scatter. Always square cells.
  Cell size computed from container dimensions. Single-pixel grid lines.
  45° diagonal column labels. Hover shows Pearson correlation.
  Optional log-log scale toggle.
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
  let hoverRow = -1;
  let hoverCol = -1;
  let observer;
  let useLog = true;

  const LABEL_W = 60;
  const HEADER_H = 60;

  $: n = fields.length;

  function cellKey(r, c) { return `${r}_${c}`; }

  function maybeLog(values) {
    if (!useLog) return values;
    return values.map(v => v > 0 ? Math.log10(v) : 0);
  }

  function computeLayout() {
    if (!outerEl || n === 0) { cellSize = 0; return; }
    const rect = outerEl.getBoundingClientRect();
    const availW = rect.width - LABEL_W;
    const availH = rect.height - HEADER_H;
    // Cell size so that N cells + (N-1) single-pixel borders fit
    cellSize = Math.max(20, Math.floor(Math.min(
      (availW - (n - 1)) / n,
      (availH - (n - 1)) / n
    )));
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
          const vals = maybeLog(fields[row].values);
          if (fieldsB) drawHistogram(ctx, maybeLog(fieldsB[row].values), 20, w, h, '#ff6b35');
          drawHistogram(ctx, vals, 20, w, h, '#4a9eff');
        } else {
          const xVals = maybeLog(fields[col].values);
          const yVals = maybeLog(fields[row].values);
          if (fieldsB) {
            drawScatter(ctx, maybeLog(fieldsB[col].values), maybeLog(fieldsB[row].values), w, h, '#ff6b35', 0.2);
          }
          drawScatter(ctx, xVals, yVals, w, h, '#4a9eff', 0.3);
        }
      }
    }
  }

  $: if (fields && n >= 0) renderAll();
  $: if (useLog !== undefined && n > 0) renderAll();

  onMount(() => {
    observer = new ResizeObserver(() => renderAll());
    if (outerEl) observer.observe(outerEl);
  });
  onDestroy(() => { if (observer) observer.disconnect(); });

  // Re-attach observer when outerEl changes (e.g. empty → grid transition)
  $: if (outerEl && observer) {
    observer.disconnect();
    observer.observe(outerEl);
    renderAll();
  }

  function onCellHover(e, row, col) {
    hoverRow = row;
    hoverCol = col;
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

  function onCellLeave() { hoverInfo = ''; hoverRow = -1; hoverCol = -1; }

  // Position of cell (row, col) — cells share borders via +1 offset per cell
  function cellLeft(col) { return LABEL_W + col * (cellSize + 1); }
  function cellTop(row) { return HEADER_H + row * (cellSize + 1); }

  $: totalW = n > 0 ? LABEL_W + n * cellSize + (n - 1) : 0;
  $: totalH = n > 0 ? HEADER_H + n * cellSize + (n - 1) : 0;
</script>

<div class="splom-outer" bind:this={outerEl}>
  {#if n > 0 && cellSize > 0}
    <div class="splom-frame" style="width: {totalW}px; height: {totalH}px;">
      <!-- Log toggle -->
      <button class="log-toggle" class:active={useLog} on:click={() => { useLog = !useLog; }}
              title={useLog ? 'Switch to linear scale' : 'Switch to log₁₀ scale'}>
        {useLog ? 'Log' : 'Lin'}
      </button>
      <!-- Column headers (45° diagonal) -->
      {#each fields as f, i}
        <span class="col-label" class:highlight={hoverCol === i}
              style="left: {cellLeft(i) + cellSize / 2}px; top: {HEADER_H - 4}px;"
              title={fieldLabel(f.key)}>{fieldLabel(f.key)}</span>
      {/each}
      <!-- Row labels -->
      {#each fields as f, i}
        <span class="row-label" class:highlight={hoverRow === i}
              style="top: {cellTop(i)}px; width: {LABEL_W - 4}px; height: {cellSize}px;"
              title={fieldLabel(f.key)}>{fieldLabel(f.key)}</span>
      {/each}
      <!-- Grid background (single-pixel lines) -->
      <div class="grid-bg" style="left: {LABEL_W}px; top: {HEADER_H}px; width: {n * cellSize + (n - 1)}px; height: {n * cellSize + (n - 1)}px;"></div>
      <!-- Cells -->
      {#each { length: n } as _, row}
        {#each { length: n } as _, col}
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div class="splom-cell" class:crosshair={hoverRow === row || hoverCol === col} class:hovered={hoverRow === row && hoverCol === col}
               style="left: {cellLeft(col)}px; top: {cellTop(row)}px; width: {cellSize}px; height: {cellSize}px;"
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
  {:else}
    <div class="splom-empty">Toggle fields in Summary view to show the scatterplot matrix.</div>
  {/if}
</div>

<style>
  .splom-outer {
    position: relative; width: 100%; height: 100%; overflow: hidden;
    display: flex; align-items: flex-start; justify-content: center;
  }
  .splom-frame {
    position: relative; flex-shrink: 0;
  }
  .log-toggle {
    position: absolute; top: 0; left: 0;
    background: var(--surface2); border: 1px solid var(--border);
    color: var(--text-dim); font-family: var(--font); font-size: var(--font-size-xxs);
    padding: 1px var(--space-sm); border-radius: var(--radius-xs); cursor: pointer;
  }
  .log-toggle.active { color: var(--accent); border-color: var(--accent); }
  .col-label {
    position: absolute;
    font-size: var(--font-size-xxs); color: var(--text-dim);
    white-space: nowrap; transform-origin: bottom left;
    transform: rotate(-45deg); transition: color 0.1s;
  }
  .col-label.highlight { color: var(--accent); }
  .row-label {
    position: absolute; left: 0;
    font-size: var(--font-size-xxs); color: var(--text-dim);
    display: flex; align-items: center; justify-content: flex-end;
    padding-right: var(--space-sm); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    transition: color 0.1s;
  }
  .row-label.highlight { color: var(--accent); }
  .grid-bg {
    position: absolute; background: var(--border);
  }
  .splom-cell {
    position: absolute;
    background: var(--bg);
    overflow: hidden;
    transition: background 0.1s;
  }
  .splom-cell.crosshair { background: var(--surface); }
  .splom-cell.hovered { background: var(--surface2); }
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
