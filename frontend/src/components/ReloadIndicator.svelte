<script>
  /**
   * Polls /api/status periodically. Shows "new data" indicator when
   * server-side cache has changed since initial snapshot.
   * Reload calls /api/reload to re-read cache, then dispatches event
   * so App.svelte can re-fetch all stores without a full page reload.
   */
  import { currentDataset } from '../lib/stores.js';
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import Popover from './widgets/Popover.svelte';

  const dispatch = createEventDispatcher();

  let initialCounts = null;
  let currentCounts = null;
  let hasNewData = false;
  let reloading = false;
  let reloadPhase = '';
  let interval;
  let dotInterval;

  async function checkStatus() {
    try {
      const resp = await fetch(`/api/status/${$currentDataset}`);
      const data = await resp.json();
      if (!initialCounts) {
        initialCounts = { ...data };
      } else {
        currentCounts = data;
        // Compare only keys that exist in BOTH snapshots to avoid false positives
        hasNewData = false;
        for (const key of Object.keys(data)) {
          if (key in initialCounts && data[key] !== initialCounts[key]) {
            hasNewData = true;
            break;
          }
        }
      }
    } catch (e) {
      console.warn('Status poll failed:', e.message);
    }
  }

  function startDots() {
    let dots = 0;
    dotInterval = setInterval(() => { dots = (dots + 1) % 4; reloadPhase = reloadPhase.replace(/\.+$/, '') + '.'.repeat(dots || 1); }, 400);
  }
  function stopDots() { clearInterval(dotInterval); }

  async function reload() {
    reloading = true;
    reloadPhase = 'Reloading server cache.';
    startDots();
    try {
      const resp = await fetch(`/api/reload/${$currentDataset}`);
      const result = await resp.json();
      if (result.status === 'ok') {
        reloadPhase = 'Refreshing stores.';
        initialCounts = null;
        currentCounts = null;
        hasNewData = false;
        await checkStatus();
        dispatch('reload');
        reloadPhase = 'Done!';
      }
    } catch (e) {
      console.error('Reload failed:', e);
      reloadPhase = 'Reload failed.';
    }
    stopDots();
    reloading = false;
  }

  // Reset when dataset changes
  $: {
    $currentDataset;
    initialCounts = null;
    currentCounts = null;
    hasNewData = false;
  }

  onMount(() => {
    checkStatus();
    interval = setInterval(checkStatus, 30000);
  });

  onDestroy(() => clearInterval(interval));

  function buildChangeDetails() {
    if (!initialCounts || !currentCounts) return '';
    const changes = [];
    for (const [key, val] of Object.entries(currentCounts)) {
      const prev = initialCounts[key];
      if (prev === undefined) continue;  // skip keys not in initial snapshot
      if (val !== prev) {
        const diff = val - prev;
        const sign = diff > 0 ? '+' : '';
        changes.push(`${key}: ${prev} → ${val} (${sign}${diff})`);
      }
    }
    return changes.length ? '<br/>' + changes.join('<br/>') : '';
  }

  $: tooltipText = reloading
    ? `<strong>${reloadPhase}</strong>`
    : hasNewData
      ? '<strong>New data available</strong>' + buildChangeDetails() + '<br/><em>Click to reload server cache</em>'
      : '<strong>Data up to date</strong><br/>Polling every 30s for new samples.';
</script>

{#if hasNewData || reloading}
  <Popover text={tooltipText}>
    <span slot="trigger">
      <button class="control reload-btn" on:click={reload}
              disabled={reloading}
              title={reloading ? 'Reloading server cache...' : 'New data available — click to reload server cache'}>
        <iconify-icon icon="mdi:refresh" inline class:icon-spin={reloading}></iconify-icon>
      </button>
    </span>
  </Popover>
{/if}

<style>
  .reload-btn { animation: pulse 2s infinite; }
  .reload-btn:disabled { animation: none; opacity: 0.7; }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }
  :global(.icon-spin) { animation: spin 0.8s linear infinite; display: inline-block; }
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
