<!--
  Word frequency histogram: vertical bars showing top N most common words.
  Horizontally scrollable to fill available width. Words centered under bars.
  Supports differential mode (A% - B%) with positive/negative bars.
-->
<script>
  import { wordFrequencies } from '../../lib/stats.js';

  export let itemsA = [];
  export let itemsB = null;

  $: freqsA = wordFrequencies(itemsA, 80);
  $: freqsB = itemsB ? wordFrequencies(itemsB, 200) : null;
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
    return diffs.slice(0, 80);
  }

  $: maxAbs = displayWords.length > 0
    ? Math.max(...displayWords.map(w => Math.abs(w.value)))
    : 1;
</script>

{#if displayWords.length > 0}
  <div class="word-chart">
    {#each displayWords as w}
      <div class="bar-col" title="{w.word}: {w.isDiff ? (w.value >= 0 ? '+' : '') + (w.value * 100).toFixed(1) + '%' : w.count}">
        <div class="bar-track">
          {#if w.isDiff && w.value < 0}
            <div class="bar bar-neg" style="height: {(Math.abs(w.value) / maxAbs) * 100}%"></div>
          {:else}
            <div class="bar bar-pos" style="height: {(w.value / maxAbs) * 100}%"></div>
          {/if}
        </div>
        <span class="word-label">{w.word}</span>
      </div>
    {/each}
  </div>
{:else}
  <div class="words-empty">No captions available for word frequency analysis.</div>
{/if}

<style>
  .word-chart {
    display: flex; gap: 1px; height: 100%;
    overflow-x: auto; overflow-y: hidden;
    align-items: flex-end; padding: 0 0 0 0;
  }
  .bar-col {
    display: flex; flex-direction: column; align-items: center;
    min-width: var(--space-xl); flex-shrink: 0; height: 100%;
  }
  .bar-track {
    flex: 1; width: var(--space-lg); display: flex; flex-direction: column;
    justify-content: flex-end; min-height: 0;
  }
  .bar {
    width: 100%; border-radius: var(--radius-xs) var(--radius-xs) 0 0;
    transition: height 0.2s; min-height: 1px;
  }
  .bar-pos { background: var(--accent); opacity: 0.6; }
  .bar-neg { background: var(--selected); opacity: 0.6; }
  .word-label {
    font-size: var(--font-size-xxs); color: var(--text-dim);
    writing-mode: vertical-rl; transform: rotate(180deg);
    max-height: 50px; overflow: hidden; text-overflow: ellipsis;
    flex-shrink: 0; padding-top: var(--space-xs);
    text-align: left;
  }
  .words-empty {
    display: flex; align-items: center; justify-content: center;
    width: 100%; height: 100%; color: var(--text-dim); font-size: var(--font-size-control);
  }
</style>
