<!--
  Word frequency histogram: single canvas, vertical bars, 45° labels.
  Cached rendering with fast hover composite (same pattern as SPLOM).
-->
<script>
  import { onMount, onDestroy, tick } from 'svelte';
  import { wordFrequencies } from '../../lib/stats.js';

  export let itemsA = [];
  export let itemsB = null;

  let canvas;
  let outerEl;
  let observer;
  let cacheCanvas = null;
  let dpr = 1;
  let scale = 1;
  let hoverIdx = -1;
  let hoverInfo = '';
  let hoverX = 0;
  let hoverY = 0;

  $: freqsA = wordFrequencies(itemsA, 150);
  $: freqsB = itemsB ? wordFrequencies(itemsB, 300) : null;
  $: displayWords = computeDisplay(freqsA, freqsB);

  function computeDisplay(fA, fB) {
    if (!fB || fB.length === 0) {
      return fA.map(w => ({ word: w.word, value: w.pct, count: w.count, isDiff: false }));
    }
    const bMap = {};
    for (const w of fB) bMap[w.word] = w.pct;
    const diffs = fA.map(w => ({
      word: w.word,
      value: w.pct - (bMap[w.word] || 0),
      count: w.count,
      isDiff: true,
    }));
    diffs.sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
    return diffs.slice(0, 150);
  }

  const BAR_W = 6;
  const BAR_GAP = 1;
  const PAD_TOP = 20;
  const LABEL_H = 70;
  const BAR_AREA_H = 120;

  $: nw = displayWords.length;
  $: totalW = nw * (BAR_W + BAR_GAP);
  $: totalH = PAD_TOP + BAR_AREA_H + LABEL_H;
  $: maxAbs = nw > 0 ? Math.max(...displayWords.map(w => Math.abs(w.value))) : 1;

  function getScale() {
    if (!outerEl || nw === 0) return 1;
    const r = outerEl.getBoundingClientRect();
    return Math.min(1, r.height / totalH);
  }

  async function buildCache() {
    await tick();
    if (nw === 0) return;

    dpr = (window.devicePixelRatio || 1) * 2;
    cacheCanvas = document.createElement('canvas');
    cacheCanvas.width = totalW * dpr;
    cacheCanvas.height = totalH * dpr;
    const ctx = cacheCanvas.getContext('2d');
    ctx.scale(dpr, dpr);

    // Bars
    for (let i = 0; i < nw; i++) {
      const w = displayWords[i];
      const x = i * (BAR_W + BAR_GAP);
      const barH = (Math.abs(w.value) / maxAbs) * BAR_AREA_H;
      const y = PAD_TOP + BAR_AREA_H - barH;
      ctx.fillStyle = (w.isDiff && w.value < 0) ? '#ff6b35' : '#4a9eff';
      ctx.globalAlpha = 0.6;
      ctx.fillRect(x, y, BAR_W, barH);
      ctx.globalAlpha = 1;
    }

    // Baseline
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, PAD_TOP + BAR_AREA_H);
    ctx.lineTo(totalW, PAD_TOP + BAR_AREA_H);
    ctx.stroke();

    // Labels (45° diagonal)
    ctx.font = '8px ' + getComputedStyle(document.body).fontFamily;
    ctx.fillStyle = '#888';
    ctx.textAlign = 'left';
    for (let i = 0; i < nw; i++) {
      const x = i * (BAR_W + BAR_GAP) + BAR_W / 2;
      const y = PAD_TOP + BAR_AREA_H + 4;
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(Math.PI / 4);
      ctx.fillText(displayWords[i].word, 0, 0);
      ctx.restore();
    }

    compositeFrame();
  }

  function compositeFrame() {
    if (!canvas || !cacheCanvas || nw === 0) return;

    canvas.width = totalW * dpr;
    canvas.height = totalH * dpr;
    canvas.style.width = totalW + 'px';
    canvas.style.height = totalH + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);

    // Hover highlight
    if (hoverIdx >= 0) {
      const x = hoverIdx * (BAR_W + BAR_GAP);
      ctx.fillStyle = 'rgba(255,255,255,0.08)';
      ctx.fillRect(x - 1, 0, BAR_W + 2, totalH);
    }

    ctx.drawImage(cacheCanvas, 0, 0, totalW * dpr, totalH * dpr, 0, 0, totalW, totalH);

    // Highlighted label
    if (hoverIdx >= 0) {
      const x = hoverIdx * (BAR_W + BAR_GAP) + BAR_W / 2;
      const y = PAD_TOP + BAR_AREA_H + 4;
      ctx.font = '8px ' + getComputedStyle(document.body).fontFamily;
      ctx.fillStyle = '#4a9eff';
      ctx.textAlign = 'left';
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(Math.PI / 4);
      ctx.fillText(displayWords[hoverIdx].word, 0, 0);
      ctx.restore();
    }
  }

  $: if (displayWords && nw >= 0) buildCache();

  $: scale = getScale();
  $: if (nw >= 0 && outerEl) scale = getScale();

  onMount(() => {
    observer = new ResizeObserver(() => { scale = getScale(); });
    if (outerEl) observer.observe(outerEl);
  });
  onDestroy(() => { if (observer) observer.disconnect(); });
  $: if (outerEl && observer) { observer.disconnect(); observer.observe(outerEl); }

  function onMove(e) {
    if (nw === 0) return;
    const rect = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left) / scale;
    const idx = Math.floor(mx / (BAR_W + BAR_GAP));
    hoverIdx = (idx >= 0 && idx < nw) ? idx : -1;
    compositeFrame();
    if (hoverIdx >= 0) {
      const w = displayWords[hoverIdx];
      hoverInfo = w.isDiff
        ? `${w.word}: ${(w.value >= 0 ? '+' : '')}${(w.value * 100).toFixed(2)}%`
        : `${w.word}: ${w.count} occurrences (${(w.value * 100).toFixed(2)}%)`;
      const outerRect = outerEl.getBoundingClientRect();
      hoverX = e.clientX - outerRect.left + 12;
      hoverY = e.clientY - outerRect.top - 8;
    } else {
      hoverInfo = '';
    }
  }

  function onLeave() { hoverIdx = -1; hoverInfo = ''; compositeFrame(); }
</script>

<div class="words-outer" bind:this={outerEl}>
  {#if nw > 0}
    <div class="words-scroll">
      <div class="words-scaled" style="transform: scale({scale}); width: {totalW}px; height: {totalH}px;">
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <canvas bind:this={canvas} on:mousemove={onMove} on:mouseleave={onLeave}></canvas>
      </div>
    </div>
    {#if hoverInfo}
      <div class="words-tip" style="left: {hoverX}px; top: {hoverY}px;">{hoverInfo}</div>
    {/if}
  {:else}
    <div class="words-empty">No captions available for word frequency analysis.</div>
  {/if}
</div>

<style>
  .words-outer { position: relative; width: 100%; height: 100%; overflow: hidden; }
  .words-scroll { width: 100%; height: 100%; overflow-x: auto; overflow-y: hidden; }
  .words-scaled { transform-origin: top left; flex-shrink: 0; }
  canvas { display: block; }
  .words-tip {
    position: absolute; pointer-events: none; z-index: 10;
    background: var(--surface2); border: 1px solid var(--border);
    color: var(--text); padding: var(--space-xs) var(--space-sm);
    border-radius: var(--radius-xs); font-size: var(--font-size-xs);
    white-space: nowrap;
  }
  .words-empty {
    display: flex; align-items: center; justify-content: center;
    width: 100%; height: 100%; color: var(--text-dim); font-size: var(--font-size-control);
  }
</style>
