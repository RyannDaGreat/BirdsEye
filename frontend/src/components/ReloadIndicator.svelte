<script>
  /**
   * Polls /api/status periodically. Shows a subtle "new data" indicator
   * when server data counts have changed since last page load/search.
   * Renders as an inline header button (same style as other controls).
   */
  import { currentDataset } from '../lib/stores.js';
  import { onMount, onDestroy } from 'svelte';
  import Popover from './widgets/Popover.svelte';

  let initialCounts = null;
  let currentCounts = null;
  let hasNewData = false;
  let interval;

  async function checkStatus() {
    try {
      const resp = await fetch(`/api/status/${$currentDataset}`);
      const data = await resp.json();
      if (!initialCounts) {
        initialCounts = data;
      } else {
        currentCounts = data;
        hasNewData = JSON.stringify(data) !== JSON.stringify(initialCounts);
      }
    } catch (e) {
      // Status polling is non-critical; log but don't interrupt
      console.warn('Status poll failed:', e.message);
    }
  }

  function reload() {
    initialCounts = null;
    hasNewData = false;
    window.location.reload();
  }

  onMount(() => {
    checkStatus();
    interval = setInterval(checkStatus, 30000); // poll every 30s
  });

  onDestroy(() => clearInterval(interval));

  $: tooltipText = hasNewData
    ? '<strong>New data available</strong><br/>The server has detected new processed samples since this page loaded. Click to reload and see the latest data.'
    : '<strong>Data up to date</strong><br/>Polling the server every 30 seconds for new processed samples. No changes detected.';
</script>

{#if hasNewData}
  <Popover text={tooltipText}>
    <span slot="trigger">
      <button class="control reload-btn active-toggle" on:click={reload}
              title="New data available — click to reload">
        <iconify-icon icon="mdi:refresh" inline></iconify-icon>
      </button>
    </span>
  </Popover>
{/if}

<style>
  .reload-btn {
    animation: pulse 2s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }
</style>
