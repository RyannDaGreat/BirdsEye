<!--
  Scatterplot Matrix (SPLOM).
  One big canvas. Expensive content (dots, histograms, grid, labels) cached
  to an offscreen canvas. Hover overlay composites cached image + crosshair.
-->
<script>
  import { onMount, onDestroy, tick } from 'svelte';
  import { drawScatter, drawHistogram } from '../../lib/canvas.js';
  import { pearsonCorrelation } from '../../lib/stats.js';
  import { fieldLabel } from '../../lib/fields.js';

  export let fields = [];
  export let fieldsB = null;

  let canvas;
  let outerEl;
  let observer;
  let useLog = true;
  let hoverInfo = '';
  let hoverX = 0;
  let hoverY = 0;
  let hoverRow = -1;
  let hoverCol = -1;

  // Offscreen cache for the expensive content
  let cacheCanvas = null;
  let dpr = 1;

  const CELL = 80;
  const PAD_LEFT = 150;
  const PAD_RIGHT = 150;
  const PAD_TOP = 150;

  $: n = fields.length;
  $: totalW = PAD_LEFT + n * CELL + PAD_RIGHT;
  $: totalH = PAD_TOP + n * CELL;

  function maybeLog(values) {
    if (!useLog) return values;
    return values.map(v => v > 0 ? Math.log10(v) : 0);
  }

  function getScale() {
    if (!outerEl || n === 0) return 1;
    const r = outerEl.getBoundingClientRect();
    return Math.min(1, r.width / totalW, r.height / totalH);
  }

  /** Render all expensive content to offscreen cache. Called once per data/log change. */
  async function buildCache() {
    await tick();
    if (n === 0) return;

    dpr = (window.devicePixelRatio || 1) * 2;
    cacheCanvas = document.createElement('canvas');
    cacheCanvas.width = totalW * dpr;
    cacheCanvas.height = totalH * dpr;
    const ctx = cacheCanvas.getContext('2d');
    ctx.scale(dpr, dpr);

    // Grid lines
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1;
    for (let i = 0; i <= n; i++) {
      const x = PAD_LEFT + i * CELL;
      ctx.beginPath(); ctx.moveTo(x, PAD_TOP); ctx.lineTo(x, PAD_TOP + n * CELL); ctx.stroke();
      const y = PAD_TOP + i * CELL;
      ctx.beginPath(); ctx.moveTo(PAD_LEFT, y); ctx.lineTo(PAD_LEFT + n * CELL, y); ctx.stroke();
    }

    // Cell contents
    for (let row = 0; row < n; row++) {
      for (let col = 0; col < n; col++) {
        const ox = PAD_LEFT + col * CELL;
        const oy = PAD_TOP + row * CELL;
        ctx.save();
        ctx.beginPath(); ctx.rect(ox, oy, CELL, CELL); ctx.clip();
        ctx.translate(ox, oy);
        if (row === col) {
          if (fieldsB) drawHistogram(ctx, maybeLog(fieldsB[row].values), 20, CELL, CELL, '#ff6b35');
          drawHistogram(ctx, maybeLog(fields[row].values), 20, CELL, CELL, '#4a9eff');
        } else {
          if (fieldsB) drawScatter(ctx, maybeLog(fieldsB[col].values), maybeLog(fieldsB[row].values), CELL, CELL, '#ff6b35', 0.2);
          drawScatter(ctx, maybeLog(fields[col].values), maybeLog(fields[row].values), CELL, CELL, '#4a9eff', 0.3);
        }
        ctx.restore();
      }
    }

    // Column labels (45° diagonal)
    ctx.font = '9px ' + getComputedStyle(document.body).fontFamily;
    ctx.textAlign = 'left';
    ctx.fillStyle = '#888';
    for (let i = 0; i < n; i++) {
      ctx.save();
      ctx.translate(PAD_LEFT + i * CELL + CELL / 2, PAD_TOP - 4);
      ctx.rotate(-Math.PI / 4);
      ctx.fillText(fieldLabel(fields[i].key), 0, 0);
      ctx.restore();
    }

    // Row labels
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#888';
    for (let i = 0; i < n; i++) {
      ctx.fillText(fieldLabel(fields[i].key), PAD_LEFT - 4, PAD_TOP + i * CELL + CELL / 2);
    }

    compositeFrame();
  }

  /** Fast composite: crosshair + cached image + highlighted labels. */
  function compositeFrame() {
    if (!canvas || !cacheCanvas || n === 0) return;

    canvas.width = totalW * dpr;
    canvas.height = totalH * dpr;
    canvas.style.width = totalW + 'px';
    canvas.style.height = totalH + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);

    // Crosshair highlight (drawn first, behind everything)
    if (hoverRow >= 0 && hoverCol >= 0) {
      ctx.fillStyle = 'rgba(255,255,255,0.04)';
      ctx.fillRect(PAD_LEFT, PAD_TOP + hoverRow * CELL, n * CELL, CELL);
      ctx.fillRect(PAD_LEFT + hoverCol * CELL, PAD_TOP, CELL, n * CELL);
      ctx.fillStyle = 'rgba(255,255,255,0.06)';
      ctx.fillRect(PAD_LEFT + hoverCol * CELL, PAD_TOP + hoverRow * CELL, CELL, CELL);
    }

    // Stamp cached content on top
    ctx.drawImage(cacheCanvas, 0, 0, totalW * dpr, totalH * dpr, 0, 0, totalW, totalH);

    // Highlighted labels (overdraw on top of cached dim labels)
    if (hoverRow >= 0 || hoverCol >= 0) {
      ctx.font = '9px ' + getComputedStyle(document.body).fontFamily;
      ctx.fillStyle = '#4a9eff';
      if (hoverCol >= 0) {
        ctx.textAlign = 'left';
        ctx.save();
        ctx.translate(PAD_LEFT + hoverCol * CELL + CELL / 2, PAD_TOP - 4);
        ctx.rotate(-Math.PI / 4);
        ctx.fillText(fieldLabel(fields[hoverCol].key), 0, 0);
        ctx.restore();
      }
      if (hoverRow >= 0) {
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        ctx.fillText(fieldLabel(fields[hoverRow].key), PAD_LEFT - 4, PAD_TOP + hoverRow * CELL + CELL / 2);
      }
    }
  }

  // Rebuild cache when data or log mode changes
  $: if (fields && n >= 0) buildCache();
  $: if (useLog !== undefined) buildCache();

  $: scale = getScale();
  $: if (n >= 0 && outerEl) scale = getScale();

  onMount(() => {
    observer = new ResizeObserver(() => { scale = getScale(); });
    if (outerEl) observer.observe(outerEl);
  });
  onDestroy(() => { if (observer) observer.disconnect(); });
  $: if (outerEl && observer) { observer.disconnect(); observer.observe(outerEl); }

  function onCanvasMove(e) {
    if (n === 0) return;
    const rect = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left) / scale;
    const my = (e.clientY - rect.top) / scale;
    const col = Math.floor((mx - PAD_LEFT) / CELL);
    const row = Math.floor((my - PAD_TOP) / CELL);
    if (row >= 0 && row < n && col >= 0 && col < n) {
      hoverRow = row; hoverCol = col;
      compositeFrame();
      if (row === col) {
        hoverInfo = `${fieldLabel(fields[row].key)}: ${fields[row].values.length} samples`;
      } else {
        const r = pearsonCorrelation(fields[col].values, fields[row].values);
        hoverInfo = `${fieldLabel(fields[col].key)} × ${fieldLabel(fields[row].key)}: r = ${r.toFixed(3)}`;
      }
      const outerRect = outerEl.getBoundingClientRect();
      hoverX = e.clientX - outerRect.left + 12;
      hoverY = e.clientY - outerRect.top - 8;
    } else if (hoverRow >= 0) {
      hoverRow = -1; hoverCol = -1; hoverInfo = '';
      compositeFrame();
    }
  }

  function onCanvasLeave() {
    if (hoverRow >= 0) { hoverRow = -1; hoverCol = -1; hoverInfo = ''; compositeFrame(); }
  }
</script>

<div class="splom-outer" bind:this={outerEl}>
  {#if n > 0}
    <div class="splom-wrap">
      <div class="splom-scaled" style="transform: scale({scale}); width: {totalW}px; height: {totalH}px;">
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <canvas bind:this={canvas} on:mousemove={onCanvasMove} on:mouseleave={onCanvasLeave}></canvas>
      </div>
    </div>
    <button class="log-toggle" class:active={useLog} on:click={() => { useLog = !useLog; }}
            title={useLog ? 'Switch to linear scale' : 'Switch to log₁₀ scale'}>
      {useLog ? 'Log' : 'Lin'}
    </button>
    {#if hoverInfo}
      <div class="splom-tip" style="left: {hoverX}px; top: {hoverY}px;">{hoverInfo}</div>
    {/if}
  {:else}
    <div class="splom-empty">Toggle fields in Summary view to show the scatterplot matrix.</div>
  {/if}
</div>

<style>
  .splom-outer { position: relative; width: 100%; height: 100%; overflow: hidden; }
  .splom-wrap { width: 100%; height: 100%; display: flex; justify-content: center; }
  .splom-scaled { transform-origin: top left; flex-shrink: 0; }
  canvas { display: block; }
  .log-toggle {
    position: absolute; top: var(--space-xs); left: var(--space-xs); z-index: 2;
    background: var(--surface2); border: 1px solid var(--border);
    color: var(--text-dim); font-family: var(--font); font-size: var(--font-size-xxs);
    padding: 1px var(--space-sm); border-radius: var(--radius-xs); cursor: pointer;
  }
  .log-toggle.active { color: var(--accent); border-color: var(--accent); }
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
