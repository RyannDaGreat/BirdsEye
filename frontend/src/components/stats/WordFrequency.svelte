<!--
  Word frequency: vertical bars with real selectable text labels.
  CSS flexbox layout, no canvas. Horizontally scrollable.
  Differential mode shows positive (accent) and negative (selected) bars.
-->
<script>
  import { wordFrequencies } from '../../lib/stats.js';

  export let itemsA = [];
  export let itemsB = null;

  let hoverIdx = -1;

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

  $: nw = displayWords.length;
  $: maxAbs = nw > 0 ? Math.max(...displayWords.map(w => Math.abs(w.value))) : 1;

  function barHeight(w) {
    return maxAbs > 0 ? (Math.abs(w.value) / maxAbs) * 100 : 0;
  }

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

<div class="words-outer">
  {#if nw > 0}
    <div class="words-scroll">
      <div class="bars-row">
        {#each displayWords as w, i}
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div class="bar-col" class:hovered={hoverIdx === i}
               on:mouseenter={() => hoverIdx = i} on:mouseleave={() => hoverIdx = -1}>
            <div class="bar-track">
              <div class="bar-fill" style="height: {barHeight(w)}%; background: {barColor(w)};"
                   title={tooltip(w)}></div>
            </div>
            <span class="bar-label">{w.word}</span>
          </div>
        {/each}
      </div>
    </div>
    {#if hoverIdx >= 0 && hoverIdx < nw}
      <div class="hover-info">{tooltip(displayWords[hoverIdx])}</div>
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
    padding: var(--space-sm) var(--space-md) 0;
  }
  .bars-row {
    display: flex; align-items: flex-end;
    height: 100%; gap: 1px;
  }
  .bar-col {
    display: flex; flex-direction: column; align-items: center;
    flex-shrink: 0; width: 7px; cursor: default;
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
    transform: rotate(180deg);
    font-size: var(--font-size-xxs); color: var(--text-dim);
    white-space: nowrap; padding-top: var(--space-xs);
    user-select: text; cursor: text;
    max-height: 60px; overflow: hidden; text-overflow: clip;
  }
  .bar-col.hovered .bar-label { color: var(--accent); }
  .hover-info {
    position: absolute; bottom: var(--space-sm); left: var(--space-md);
    background: var(--surface2); border: 1px solid var(--border);
    color: var(--text); padding: var(--space-xs) var(--space-sm);
    border-radius: var(--radius-xs); font-size: var(--font-size-xs);
    white-space: nowrap; pointer-events: none;
  }
  .words-empty {
    display: flex; align-items: center; justify-content: center;
    width: 100%; height: 100%; color: var(--text-dim); font-size: var(--font-size-control);
  }
</style>
