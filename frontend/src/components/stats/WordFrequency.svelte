<!--
  Word frequency: vertical bars with real selectable text labels.
  CSS flexbox layout, no canvas. Horizontally scrollable.
  Differential mode shows positive (accent) and negative (selected) bars.
-->
<script>
  import { wordFrequencies, captionWords } from '../../lib/stats.js';
  import { tipPos } from '../../lib/format.js';
  import { hoveredItem, hoveredWord } from '../../lib/stores.js';

  export let itemsA = [];
  export let itemsB = null;
  export let useLog = false;

  const MAX_WORDS = 150;       // max words to display
  const MAX_WORDS_DIFF = 300;  // larger pool for differential mode (sorted + sliced to MAX_WORDS)

  let hoverIdx = -1;
  let tipX = 0;
  let tipY = 0;
  let outerEl;

  // Words from hovered video card's caption (for highlighting matching bars)
  $: hoveredCaptionWords = $hoveredItem ? captionWords($hoveredItem.caption) : new Set();

  function onColEnter(i, e) {
    hoverIdx = i;
    $hoveredWord = displayWords[i]?.word || null;
    updateTip(e);
  }
  function onColMove(e) { updateTip(e); }
  function updateTip(e) {
    const p = tipPos(e);
    tipX = p.x;
    tipY = p.y;
  }

  $: freqsA = wordFrequencies(itemsA, MAX_WORDS);
  $: freqsB = itemsB ? wordFrequencies(itemsB, MAX_WORDS_DIFF) : null;
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
    return diffs.slice(0, MAX_WORDS);
  }

  $: nw = displayWords.length;
  $: maxAbs = nw > 0 ? Math.max(...displayWords.map(w => Math.abs(w.value))) : 1;
  $: maxWordLen = nw > 0 ? Math.max(...displayWords.map(w => w.word.length)) : 0;
  // ~5.5px per character at font-size-xxs (9px) in vertical mode, plus padding
  $: labelH = Math.max(30, maxWordLen * 5.5 + 4);

  // Precompute bar heights reactively so Svelte tracks useLog dependency.
  // Log mode uses counts (which span orders of magnitude: 5 to 500+).
  // Linear mode uses percentage values (all similar magnitude, shows proportional differences).
  $: barHeights = (() => {
    if (useLog) {
      const logVals = displayWords.map(w => w.count > 0 ? Math.log10(w.count) : 0);
      const lmax = Math.max(...logVals, 0);
      return logVals.map(lv => lmax > 0 ? (lv / lmax) * 100 : 0);
    }
    return displayWords.map(w => maxAbs > 0 ? (Math.abs(w.value) / maxAbs) * 100 : 0);
  })();

  function barColor(w) {
    return (w.isDiff && w.value < 0) ? 'var(--selected)' : 'var(--accent)';
  }

  function tooltip(w) {
    if (w.isDiff) {
      return `${w.word}: ${w.value >= 0 ? '+' : ''}${(w.value * 100).toFixed(2)}%`;
    }
    return `${w.word}: ${w.count} (${(w.value * 100).toFixed(2)}%)`;
  }
</script>

<div class="words-outer" bind:this={outerEl}>
  {#if nw > 0}
    <div class="words-scroll">
      <div class="bars-row">
        {#each displayWords as w, i}
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div class="bar-col" class:hovered={hoverIdx === i}
               class:caption-match={hoveredCaptionWords.has(w.word)}
               on:mouseenter={(e) => onColEnter(i, e)}
               on:mousemove={onColMove}
               on:mouseleave={() => { hoverIdx = -1; $hoveredWord = null; }}>
            <div class="bar-track">
              <div class="bar-fill" style="height: {barHeights[i]}%; background: {barColor(w)};"></div>
            </div>
            <span class="bar-label" style="height: {labelH}px;">{w.word}</span>
          </div>
        {/each}
      </div>
    </div>
    {#if hoverIdx >= 0 && hoverIdx < nw}
      <div class="mouse-tip" style="left: {tipX}px; top: {tipY}px;">{tooltip(displayWords[hoverIdx])}</div>
    {/if}
  {:else}
    <div class="words-empty">No captions available.</div>
  {/if}
</div>

<style>
  .words-outer {
    position: relative; width: 100%; height: 100%;
    display: flex; flex-direction: column; overflow: hidden;
  }
  .words-scroll {
    flex: 1; min-height: 0;
    overflow-x: auto; overflow-y: hidden;
  }
  .bars-row {
    display: flex;
    height: 100%;
  }
  .bar-col {
    display: flex; flex-direction: column; align-items: center;
    flex-shrink: 0; width: 8px; padding: 0 0.5px; cursor: default;
    height: 100%;
  }
  .bar-col.hovered { background: rgba(255,255,255,0.05); }
  .bar-track {
    flex: 1; min-height: 0; width: 100%;
    display: flex; flex-direction: column; justify-content: flex-end;
    border-bottom: 1px solid var(--border);
  }
  .bar-fill {
    width: 100%; opacity: 0.6;
    transition: opacity 0.1s;
  }
  .bar-col.hovered .bar-fill { opacity: 0.9; }
  .bar-label {
    writing-mode: vertical-lr;
    font-size: var(--font-size-xxs); color: var(--text-dim);
    white-space: nowrap;
    user-select: text; cursor: text;
    flex-shrink: 0; overflow: hidden;
  }
  .bar-col.hovered .bar-label { color: var(--accent); }
  .bar-col.caption-match { background: rgba(255,255,255,0.05); }
  .bar-col.caption-match .bar-fill { opacity: 0.9; }
  .bar-col.caption-match .bar-label { color: var(--accent); }
  .words-empty {
    display: flex; align-items: center; justify-content: center;
    width: 100%; height: 100%; color: var(--text-dim); font-size: var(--font-size-control);
  }
</style>
