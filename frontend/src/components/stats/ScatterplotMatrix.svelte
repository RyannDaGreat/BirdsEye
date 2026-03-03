<!--
  Scatterplot Matrix (SPLOM).
  One big canvas. Expensive content (dots, histograms, grid, labels) cached
  to an offscreen canvas. Hover overlay composites cached image + crosshair.
-->
<script>
  import { onMount, onDestroy, tick } from 'svelte';
  import { drawScatter, drawHistogram, findAlphaBounds } from '../../lib/canvas.js';
  import { pearsonCorrelation } from '../../lib/stats.js';
  import { fieldLabel } from '../../lib/fields.js';
  import { tipPos } from '../../lib/format.js';
  import { hoveredFields, hoveredItem } from '../../lib/stores.js';
  import { getNestedValue } from '../../lib/sort.js';

  export let fields = [];
  export let fieldsB = null;

  export let useLog = true;

  let canvas;
  let outerEl;
  let observer;
  let hoverInfo = '';
  let hoverX = 0;
  let hoverY = 0;
  let hoverRow = -1;
  let hoverCol = -1;
  let localHover = false;  // true when mouse is over canvas (prevents reacting to own hoveredFields changes)

  // Offscreen cache for the expensive content
  let cacheCanvas = null;
  let dpr = 1;
  // Alpha-crop bounding box (logical pixels in the full cache canvas)
  let crop = { x: 0, y: 0, w: 0, h: 0 };

  const CELL = 80;
  const HIST_BINS = 20;
  const LABEL_FONT_SIZE = 14;
  const PAD_LEFT = 150;
  const PAD_RIGHT = 150;
  const PAD_TOP = 150;
  const DOT_PAD = 2;  // matches drawScatter pad
  const DOT_RADIUS = 3;

  /**
   * Map a raw value to a pixel position within a CELL, matching drawScatter's normalization.
   * Pure function.
   *
   * @param {number} val - the value to position
   * @param {number[]} allValues - all values in the field (for min/max)
   * @param {boolean} isY - true for Y axis (inverted), false for X axis
   * @returns {number} pixel offset within the cell
   *
   * >>> // Conceptually: value at midpoint of range → middle of cell
   */
  function valToCell(val, allValues, isY) {
    const vals = maybeLog(allValues);
    const v = (useLog && val > 0) ? Math.log10(val) : val;
    const mn = Math.min(...vals);
    const mx = Math.max(...vals);
    const range = mx - mn || 1;
    const drawSize = CELL - DOT_PAD * 2;
    const frac = (v - mn) / range;
    return isY ? (CELL - DOT_PAD - frac * drawSize) : (DOT_PAD + frac * drawSize);
  }

  $: n = fields.length;
  $: totalW = PAD_LEFT + n * CELL + PAD_RIGHT;
  $: totalH = PAD_TOP + n * CELL;

  function maybeLog(values) {
    if (!useLog) return values;
    return values.map(v => v > 0 ? Math.log10(v) : 0);
  }

  function getScale() {
    if (!outerEl || n === 0 || crop.w === 0 || crop.h === 0) return 1;
    const r = outerEl.getBoundingClientRect();
    return Math.min(1, r.width / crop.w, r.height / crop.h);
  }

  // Read CSS theme colors once for canvas rendering
  function cssVar(name) { return getComputedStyle(document.body).getPropertyValue(name).trim(); }

  /** Render all expensive content to offscreen cache. Called once per data/log change. */
  async function buildCache() {
    await tick();
    if (n === 0) return;

    const colorAccent = cssVar('--accent');
    const colorSelected = cssVar('--selected');
    const colorBorder = cssVar('--border');
    const colorDim = cssVar('--text-dim');

    dpr = (window.devicePixelRatio || 1) * 2;
    cacheCanvas = document.createElement('canvas');
    cacheCanvas.width = totalW * dpr;
    cacheCanvas.height = totalH * dpr;
    const ctx = cacheCanvas.getContext('2d');
    ctx.scale(dpr, dpr);

    // Grid lines
    ctx.strokeStyle = colorBorder;
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
          if (fieldsB) drawHistogram(ctx, maybeLog(fieldsB[row].values), HIST_BINS, CELL, CELL, colorSelected);
          drawHistogram(ctx, maybeLog(fields[row].values), HIST_BINS, CELL, CELL, colorAccent);
        } else {
          if (fieldsB) drawScatter(ctx, maybeLog(fieldsB[col].values), maybeLog(fieldsB[row].values), CELL, CELL, colorSelected, 0.2);
          drawScatter(ctx, maybeLog(fields[col].values), maybeLog(fields[row].values), CELL, CELL, colorAccent, 0.3);
        }
        ctx.restore();
      }
    }

    // Column labels (45° diagonal)
    ctx.font = LABEL_FONT_SIZE + 'px ' + getComputedStyle(document.body).fontFamily;
    ctx.textAlign = 'left';
    ctx.fillStyle = colorDim;
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
    ctx.fillStyle = colorDim;
    for (let i = 0; i < n; i++) {
      ctx.fillText(fieldLabel(fields[i].key), PAD_LEFT - 4, PAD_TOP + i * CELL + CELL / 2);
    }

    // Alpha-crop: find tight bounding box of rendered content
    const bounds = findAlphaBounds(cacheCanvas, dpr);
    // Small padding around content for breathing room
    const pad = 2;
    crop = {
      x: Math.max(0, bounds.x - pad),
      y: Math.max(0, bounds.y - pad),
      w: Math.min(totalW - Math.max(0, bounds.x - pad), bounds.w + pad * 2),
      h: Math.min(totalH - Math.max(0, bounds.y - pad), bounds.h + pad * 2),
    };

    scale = getScale();
    compositeFrame();
  }

  /** Fast composite: crosshair + cached image + highlighted labels.
   *  All drawing uses original (pre-crop) coordinates via ctx.translate(-crop.x, -crop.y).
   *  The visible canvas is sized to the crop region. */
  function compositeFrame() {
    if (!canvas || !cacheCanvas || n === 0 || crop.w === 0) return;

    canvas.width = crop.w * dpr;
    canvas.height = crop.h * dpr;
    canvas.style.width = crop.w + 'px';
    canvas.style.height = crop.h + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    // Shift so we can use original coordinates (labels, grid, etc.)
    ctx.translate(-crop.x, -crop.y);

    // Dark base for entire grid area (slightly darker than surrounding)
    ctx.fillStyle = 'rgba(0,0,0,0.15)';
    ctx.fillRect(PAD_LEFT, PAD_TOP, n * CELL, n * CELL);

    // Crosshair highlight (even darker)
    if (hoverRow >= 0 && hoverRow < n && hoverCol >= 0 && hoverCol < n) {
      ctx.fillStyle = 'rgba(0,0,0,0.15)';
      ctx.fillRect(PAD_LEFT, PAD_TOP + hoverRow * CELL, n * CELL, CELL);
      ctx.fillRect(PAD_LEFT + hoverCol * CELL, PAD_TOP, CELL, n * CELL);
      // Hovered cell: fully black
      ctx.fillStyle = 'rgba(0,0,0,0.4)';
      ctx.fillRect(PAD_LEFT + hoverCol * CELL, PAD_TOP + hoverRow * CELL, CELL, CELL);
    }

    // Stamp cached content on top (draw full cache, translate clips to visible region)
    ctx.drawImage(cacheCanvas, 0, 0, totalW * dpr, totalH * dpr, 0, 0, totalW, totalH);

    // Highlighted labels (overdraw on top of cached dim labels)
    if ((hoverRow >= 0 && hoverRow < n) || (hoverCol >= 0 && hoverCol < n)) {
      ctx.font = LABEL_FONT_SIZE + 'px ' + getComputedStyle(document.body).fontFamily;
      ctx.fillStyle = cssVar('--accent');
      if (hoverCol >= 0 && hoverCol < n) {
        ctx.textAlign = 'left';
        ctx.save();
        ctx.translate(PAD_LEFT + hoverCol * CELL + CELL / 2, PAD_TOP - 4);
        ctx.rotate(-Math.PI / 4);
        ctx.fillText(fieldLabel(fields[hoverCol].key), 0, 0);
        ctx.restore();
      }
      if (hoverRow >= 0 && hoverRow < n) {
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        ctx.fillText(fieldLabel(fields[hoverRow].key), PAD_LEFT - 4, PAD_TOP + hoverRow * CELL + CELL / 2);
      }
    }

    // Hovered video item dot overlay — white dots/lines showing where this item falls
    if (hoveredVals) {
      ctx.fillStyle = '#fff';
      ctx.strokeStyle = 'rgba(0,0,0,0.8)';
      ctx.lineWidth = 1;
      for (let row = 0; row < n; row++) {
        const rKey = fields[row].key;
        const rVal = hoveredVals[rKey];
        if (rVal === undefined) continue;
        for (let col = 0; col < n; col++) {
          const ox = PAD_LEFT + col * CELL;
          const oy = PAD_TOP + row * CELL;
          if (row === col) {
            // Diagonal: vertical indicator line on histogram
            const px = ox + valToCell(rVal, fields[row].values, false);
            ctx.save();
            ctx.setLineDash([2, 2]);
            ctx.strokeStyle = 'rgba(255,255,255,0.8)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(px, oy); ctx.lineTo(px, oy + CELL);
            ctx.stroke();
            ctx.restore();
            continue;
          }
          const cKey = fields[col].key;
          const cVal = hoveredVals[cKey];
          if (cVal === undefined) continue;
          const px = ox + valToCell(cVal, fields[col].values, false);
          const py = oy + valToCell(rVal, fields[row].values, true);
          ctx.beginPath();
          ctx.arc(px, py, DOT_RADIUS, 0, Math.PI * 2);
          ctx.fill();
          ctx.stroke();
        }
      }
    }
  }

  // Reset stale hover indices when fields change
  $: if (n >= 0) { hoverRow = -1; hoverCol = -1; hoverInfo = ''; }
  // Rebuild cache when data or log mode changes
  $: if (fields && n >= 0) buildCache();
  $: if (useLog !== undefined) buildCache();

  $: scale = getScale();
  $: if (n >= 0 && outerEl) scale = getScale();
  $: offsetY = outerEl && crop.h > 0 ? Math.max(0, (outerEl.getBoundingClientRect().height - crop.h * scale) / 2) : 0;

  onMount(() => {
    observer = new ResizeObserver(() => {
      scale = getScale();
      offsetY = outerEl && crop.h > 0 ? Math.max(0, (outerEl.getBoundingClientRect().height - crop.h * scale) / 2) : 0;
    });
    if (outerEl) observer.observe(outerEl);
  });
  onDestroy(() => { if (observer) observer.disconnect(); });
  $: if (outerEl && observer) { observer.disconnect(); observer.observe(outerEl); }

  // React to hovered video item — extract field values for dot overlay
  $: hoveredVals = (() => {
    if (!$hoveredItem || n === 0) return null;
    const vals = {};
    for (const f of fields) {
      const v = getNestedValue($hoveredItem, f.key);
      if (v !== null && v !== undefined && !isNaN(Number(v))) vals[f.key] = Number(v);
    }
    return Object.keys(vals).length > 0 ? vals : null;
  })();
  $: if (hoveredVals !== undefined && cacheCanvas) compositeFrame();

  // React to external hoveredFields changes (from field bars, histograms)
  $: {
    if (!localHover && cacheCanvas && n > 0) {
      const hf = $hoveredFields;
      if (hf.size > 0) {
        const indices = [];
        for (const key of hf) {
          const idx = fields.findIndex(f => f.key === key);
          if (idx >= 0) indices.push(idx);
        }
        if (indices.length === 1) {
          hoverRow = indices[0]; hoverCol = indices[0];
        } else if (indices.length >= 2) {
          hoverRow = indices[0]; hoverCol = indices[1];
        }
        compositeFrame();
      } else if (hoverRow >= 0) {
        hoverRow = -1; hoverCol = -1;
        compositeFrame();
      }
    }
  }

  function onCanvasMove(e) {
    if (n === 0) return;
    localHover = true;
    const rect = canvas.getBoundingClientRect();
    // Convert display coords to original (pre-crop) coords
    const mx = (e.clientX - rect.left) / scale + crop.x;
    const my = (e.clientY - rect.top) / scale + crop.y;
    const col = Math.floor((mx - PAD_LEFT) / CELL);
    const row = Math.floor((my - PAD_TOP) / CELL);
    if (row >= 0 && row < n && col >= 0 && col < n) {
      hoverRow = row; hoverCol = col;
      // Cross-component highlight: both row and col fields (or just one on diagonal)
      const hset = row === col ? new Set([fields[row].key]) : new Set([fields[row].key, fields[col].key]);
      $hoveredFields = hset;
      compositeFrame();
      if (row === col) {
        hoverInfo = `${fieldLabel(fields[row].key)}: ${fields[row].values.length} samples`;
      } else {
        const r = pearsonCorrelation(fields[col].values, fields[row].values);
        hoverInfo = `${fieldLabel(fields[col].key)} × ${fieldLabel(fields[row].key)}: r = ${r.toFixed(3)}`;
      }
      const tp = tipPos(e);
      hoverX = tp.x;
      hoverY = tp.y;
    } else if (hoverRow >= 0) {
      hoverRow = -1; hoverCol = -1; hoverInfo = '';
      $hoveredFields = new Set();
      compositeFrame();
    }
  }

  function onCanvasLeave() {
    localHover = false;
    if (hoverRow >= 0) { hoverRow = -1; hoverCol = -1; hoverInfo = ''; $hoveredFields = new Set(); compositeFrame(); }
  }
</script>

<div class="splom-outer" bind:this={outerEl}>
  {#if n > 0}
    <div class="splom-scaled" style="transform: translate(0, {offsetY}px) scale({scale}); width: {crop.w}px; height: {crop.h}px;">
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <canvas bind:this={canvas} on:mousemove={onCanvasMove} on:mouseleave={onCanvasLeave}></canvas>
    </div>
    {#if hoverInfo}
      <div class="mouse-tip" style="left: {hoverX}px; top: {hoverY}px;">{hoverInfo}</div>
    {/if}
  {:else}
    <div class="splom-empty">Select fields in the Analysis column to show the scatterplot matrix.</div>
  {/if}
</div>

<style>
  .splom-outer { position: relative; width: 100%; height: 100%; overflow: hidden; }
  .splom-scaled { transform-origin: top left; }
  canvas { display: block; }
  .splom-empty {
    display: flex; align-items: center; justify-content: center;
    width: 100%; height: 100%; color: var(--text-dim); font-size: var(--font-size-control);
  }
</style>
