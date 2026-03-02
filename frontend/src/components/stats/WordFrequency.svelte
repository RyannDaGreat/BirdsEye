<!--
  Word frequency histogram: shows top N most common words in captions.
  Supports differential mode (A% - B%) with positive/negative bars.
-->
<script>
  import { wordFrequencies } from '../../lib/stats.js';

  export let itemsA = [];     // primary data source items
  export let itemsB = null;   // comparison items, or null

  $: freqsA = wordFrequencies(itemsA, 30);
  $: freqsB = itemsB ? wordFrequencies(itemsB, 100) : null;

  // In differential mode, compute (A% - B%) and sort by magnitude
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
    // Sort by absolute value descending, positives first
    diffs.sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
    return diffs.slice(0, 30);
  }

  $: maxAbs = displayWords.length > 0
    ? Math.max(...displayWords.map(w => Math.abs(w.value)))
    : 1;
</script>

{#if displayWords.length > 0}
  <div class="word-list">
    {#each displayWords as w}
      <div class="word-row">
        <span class="word-label">{w.word}</span>
        <div class="bar-container">
          {#if w.isDiff}
            {#if w.value >= 0}
              <div class="bar bar-pos" style="width: {(w.value / maxAbs) * 100}%"></div>
            {:else}
              <div class="bar bar-neg" style="width: {(Math.abs(w.value) / maxAbs) * 100}%"></div>
            {/if}
          {:else}
            <div class="bar bar-pos" style="width: {(w.value / maxAbs) * 100}%"></div>
          {/if}
        </div>
        <span class="word-count">{w.isDiff ? (w.value >= 0 ? '+' : '') + (w.value * 100).toFixed(1) + '%' : w.count}</span>
      </div>
    {/each}
  </div>
{:else}
  <div class="words-empty">No captions available for word frequency analysis.</div>
{/if}

<style>
  .word-list { display: flex; flex-direction: column; gap: 1px; overflow-y: auto; height: 100%; }
  .word-row { display: flex; align-items: center; gap: var(--space-sm); padding: 1px var(--space-sm); }
  .word-label { width: 80px; text-align: right; font-size: var(--font-size-xs); color: var(--text-dim); overflow: hidden; text-overflow: ellipsis; flex-shrink: 0; }
  .bar-container { flex: 1; height: var(--space-lg); background: var(--bg); border-radius: var(--radius-xs); overflow: hidden; }
  .bar { height: 100%; border-radius: var(--radius-xs); transition: width 0.2s; }
  .bar-pos { background: var(--accent); opacity: 0.6; }
  .bar-neg { background: var(--selected); opacity: 0.6; }
  .word-count { width: 50px; font-size: var(--font-size-xxs); color: var(--text-dim); text-align: right; flex-shrink: 0; }
  .words-empty {
    display: flex; align-items: center; justify-content: center;
    height: 100%; color: var(--text-dim); font-size: var(--font-size-control);
  }
</style>
