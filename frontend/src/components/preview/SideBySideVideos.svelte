<!--
  Generic: N videos side by side with labels. Wraps to multiple rows.
  Args:
    files       — filenames in sample dir
    labels      — display names per file
    max_per_row — max videos per row (default 3)
    sync        — if true, play/pause/seek syncs across all videos
    show_filesize — if true, fetch and show file sizes next to labels
-->
<script>
  import { currentDataset } from '../../lib/stores.js';
  import { humanFilesize } from '../../lib/format.js';

  export let videoName = '';
  export let args = {};

  $: allFiles = args.files || [];
  $: allLabels = args.labels || allFiles;
  $: maxPerRow = args.max_per_row || 3;
  $: showFilesize = args.show_filesize || false;
  $: doSync = args.sync || false;

  // Only show files that exist (non-404)
  let existingIndices = [];
  let fileSizes = {};
  let videoEls = [];
  let syncing = false;

  async function probeFiles(dataset, vName, files) {
    if (!dataset || !vName || !files.length) return;

    // Fetch file sizes from backend
    const resp = await fetch(`/api/file_sizes/${dataset}/${vName}`);
    if (!resp.ok) return;
    const sizes = await resp.json();
    fileSizes = sizes;

    // Only include files that have a size entry (they exist on disk)
    existingIndices = [];
    for (let i = 0; i < files.length; i++) {
      if (sizes[files[i]] !== undefined) {
        existingIndices.push(i);
      }
    }
  }

  $: probeFiles($currentDataset, videoName, allFiles);

  // Video sync logic
  function onPlay(idx) {
    if (!doSync || syncing) return;
    syncing = true;
    for (let i = 0; i < videoEls.length; i++) {
      if (i !== idx && videoEls[i]) {
        videoEls[i].currentTime = videoEls[idx].currentTime;
        videoEls[i].play();
      }
    }
    syncing = false;
  }

  function onPause(idx) {
    if (!doSync || syncing) return;
    syncing = true;
    for (let i = 0; i < videoEls.length; i++) {
      if (i !== idx && videoEls[i]) {
        videoEls[i].pause();
        videoEls[i].currentTime = videoEls[idx].currentTime;
      }
    }
    syncing = false;
  }

  function onSeeked(idx) {
    if (!doSync || syncing) return;
    syncing = true;
    for (let i = 0; i < videoEls.length; i++) {
      if (i !== idx && videoEls[i]) {
        videoEls[i].currentTime = videoEls[idx].currentTime;
      }
    }
    syncing = false;
  }
</script>

<div class="grid" style="--max-per-row: {maxPerRow}">
  {#each existingIndices as fileIdx, vidIdx}
    {@const file = allFiles[fileIdx]}
    {@const label = allLabels[fileIdx]}
    {@const size = fileSizes[file]}
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
             on:play={() => onPlay(vidIdx)}
             on:pause={() => onPause(vidIdx)}
             on:seeked={() => onSeeked(vidIdx)}
             loop muted controls preload="metadata">
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
