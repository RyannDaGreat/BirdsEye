<!--
  Word frequency histogram: vertical bars showing top N most common words.
  Words on x-axis (bottom labels), bar height = frequency.
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
    diffs.sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
    return diffs.slice(0, 30);
  }

  $: maxAbs = displayWords.length > 0
    ? Math.max(...displayWords.map(w => Math.abs(w.value)))
    : 1;
</script>

{#if displayWords.length > 0}
  <div class="word-chart">
    <div class="bars-row">
      {#each displayWords as w}
        <div class="bar-col">
          <div class="bar-track">
            {#if w.isDiff && w.value < 0}
              <div class="bar bar-neg" style="height: {(Math.abs(w.value) / maxAbs) * 100}%"></div>
            {:else}
              <div class="bar bar-pos" style="height: {(w.value / maxAbs) * 100}%"></div>
            {/if}
          </div>
        </div>
      {/each}
    </div>
    <div class="labels-row">
      {#each displayWords as w}
        <div class="word-label" title="{w.word}: {w.isDiff ? (w.value >= 0 ? '+' : '') + (w.value * 100).toFixed(1) + '%' : w.count}">{w.word}</div>
      {/each}
    </div>
  </div>
{:else}
  <div class="words-empty">No captions available for word frequency analysis.</div>
{/if}

<style>
  .word-chart { display: flex; flex-direction: column; height: 100%; overflow-x: auto; }
  .bars-row {
    flex: 1; display: flex; gap: 1px; align-items: flex-end;
    padding: var(--space-sm) 0; min-height: 0;
  }
  .bar-col { flex: 1; min-width: var(--space-lg); display: flex; flex-direction: column; justify-content: flex-end; height: 100%; }
  .bar-track { width: 100%; display: flex; flex-direction: column; justify-content: flex-end; height: 100%; }
  .bar { width: 100%; border-radius: var(--radius-xs) var(--radius-xs) 0 0; transition: height 0.2s; }
  .bar-pos { background: var(--accent); opacity: 0.6; }
  .bar-neg { background: var(--selected); opacity: 0.6; }
  .labels-row {
    display: flex; gap: 1px; flex-shrink: 0;
    border-top: 1px solid var(--border); padding-top: var(--space-xs);
  }
  .word-label {
    flex: 1; min-width: var(--space-lg);
    font-size: var(--font-size-xxs); color: var(--text-dim);
    text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    writing-mode: vertical-rl; transform: rotate(180deg); height: 60px;
  }
  .words-empty {
    display: flex; align-items: center; justify-content: center;
    height: 100%; color: var(--text-dim); font-size: var(--font-size-control);
  }
</style>
