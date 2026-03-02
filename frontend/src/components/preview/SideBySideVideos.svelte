<!--
  Generic: N videos side by side with labels. Wraps to multiple rows.
  Args:
    files       — filenames in sample dir
    labels      — display names per file
    max_per_row — max videos per row (default 3)
    sync        — if true, first video is master; others follow via RAF drift correction
    show_filesize — if true, fetch and show file sizes next to labels
-->
<script>
  import { currentDataset } from '../../lib/stores.js';
  import { humanFilesize } from '../../lib/format.js';
  import { onMount, onDestroy } from 'svelte';

  export let videoName = '';
  export let args = {};

  $: allFiles = args.files || [];
  $: allLabels = args.labels || allFiles;
  $: maxPerRow = args.max_per_row || 3;
  $: showFilesize = args.show_filesize || false;
  $: doSync = args.sync || false;

  let existingIndices = [];
  let fileSizes = {};
  let videoEls = [];
  let rafId = null;

  async function probeFiles(dataset, vName, files) {
    if (!dataset || !vName || !files.length) return;
    const resp = await fetch(`/api/file_sizes/${dataset}/${vName}`);
    if (!resp.ok) return;
    const sizes = await resp.json();
    fileSizes = sizes;
    existingIndices = [];
    for (let i = 0; i < files.length; i++) {
      if (sizes[files[i]] !== undefined) {
        existingIndices.push(i);
      }
    }
  }

  $: probeFiles($currentDataset, videoName, allFiles);

  /**
   * Master-slave video sync via requestAnimationFrame.
   * First video is the master (has controls). Others are slaves (no controls).
   * RAF loop checks drift every frame; only corrects when drift > 100ms.
   * No event listeners on slaves — eliminates feedback loops and flickering.
   */
  function startSync() {
    if (!doSync || videoEls.length < 2) return;
    const master = videoEls[0];
    if (!master) return;

    // Mirror master play/pause to slaves
    master.addEventListener('play', syncPlay);
    master.addEventListener('pause', syncPause);

    // RAF drift-correction loop
    function tick() {
      if (!master) return;
      for (let i = 1; i < videoEls.length; i++) {
        const slave = videoEls[i];
        if (!slave || slave.readyState < 2) continue;
        if (Math.abs(slave.currentTime - master.currentTime) > 0.1) {
          slave.currentTime = master.currentTime;
        }
      }
      rafId = requestAnimationFrame(tick);
    }
    rafId = requestAnimationFrame(tick);
  }

  function syncPlay() {
    for (let i = 1; i < videoEls.length; i++) {
      if (videoEls[i]) videoEls[i].play();
    }
  }

  function syncPause() {
    for (let i = 1; i < videoEls.length; i++) {
      if (videoEls[i]) {
        videoEls[i].pause();
        videoEls[i].currentTime = videoEls[0].currentTime;
      }
    }
  }

  function stopSync() {
    if (rafId) cancelAnimationFrame(rafId);
    rafId = null;
    const master = videoEls[0];
    if (master) {
      master.removeEventListener('play', syncPlay);
      master.removeEventListener('pause', syncPause);
    }
  }

  // Start sync after elements are bound
  $: if (doSync && existingIndices.length > 1 && videoEls.length > 1) {
    stopSync();
    // Tick delay lets Svelte finish binding videoEls
    setTimeout(startSync, 50);
  }

  onDestroy(stopSync);
</script>

<div class="grid" style="--max-per-row: {maxPerRow}">
  {#each existingIndices as fileIdx, vidIdx}
    {@const file = allFiles[fileIdx]}
    {@const label = allLabels[fileIdx]}
    {@const size = fileSizes[file]}
    {@const isMaster = doSync && vidIdx === 0}
    <div class="cell">
      {#if label}
        <div class="label">
          {label}
          {#if showFilesize && size !== undefined}
            <span class="filesize">{humanFilesize(size)}</span>
          {/if}
        </div>
      {/if}
      <!-- svelte-ignore a11y-media-has-caption -->
      <video src="/thumbnails/{$currentDataset}/{videoName}/{file}"
             bind:this={videoEls[vidIdx]}
             loop muted controls={!doSync || isMaster} preload="metadata">
      </video>
    </div>
  {/each}
</div>

<style>
  .grid {
    display: flex; gap: var(--space-sm); flex-wrap: wrap;
  }
  .cell {
    flex: 1 1 calc(100% / var(--max-per-row) - var(--space-sm));
    min-width: calc(100% / var(--max-per-row) - var(--space-sm));
    max-width: calc(100% / var(--max-per-row) - var(--space-sm));
    text-align: center;
  }
  video { width: 100%; border-radius: var(--radius); background: var(--black); }
  .label { font-size: var(--font-size-xs); color: var(--text-dim); margin-bottom: var(--space-xs); }
  .filesize { opacity: 0.5; margin-left: var(--space-xs); }
</style>
