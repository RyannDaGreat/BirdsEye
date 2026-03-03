<!--
  Reusable download button with size estimation, spinner, and status messages.

  Props:
    dataset    — dataset name (e.g., "pexels")
    videoNames — array of video names to download
    artifact   — specific artifact filename, or null for full sample folders
    compact    — if true, show shorter label

  Behavior:
    - Fetches estimated download size when videoNames/artifact change
    - Shows "Download (N) — 42.3MB" with mdi:download icon
    - While downloading: spinner icon + status text from downloadSamples
    - Uses shared downloadSamples() from api.js
-->
<script>
  import { writable } from 'svelte/store';
  import { downloadSamples, fetchDownloadSize } from '../../lib/api.js';
  import { humanFilesize } from '../../lib/format.js';
  import { currentDataset } from '../../lib/stores.js';
  import Popover from './Popover.svelte';

  export let dataset = '';
  export let videoNames = [];
  export let artifact = null;
  export let compact = false;

  const status = writable('');
  let sizeText = '';
  let sizeLoading = false;

  $: effectiveDataset = dataset || $currentDataset;
  $: count = videoNames.length;
  $: effectiveArtifact = artifact || null;
  $: if (count > 0) fetchSize(effectiveDataset, videoNames, effectiveArtifact);
  $: if (count === 0) sizeText = '';

  async function fetchSize(ds, names, art) {
    sizeLoading = true;
    sizeText = '';
    try {
      const { total_bytes } = await fetchDownloadSize(ds, names, art);
      sizeText = humanFilesize(total_bytes);
    } catch {
      sizeText = '';
    }
    sizeLoading = false;
  }

  async function doDownload() {
    if (count === 0 || $status) return;
    await downloadSamples(effectiveDataset, videoNames, effectiveArtifact, status);
  }

  $: downloading = !!$status;
  $: label = compact
    ? `${count}${sizeText ? ' · ' + sizeText : ''}`
    : `Download (${count})${sizeText ? ' · ' + sizeText : ''}`;
  $: tooltip = $status
    ? $status
    : `Download ${count} ${effectiveArtifact || 'sample'}${count > 1 ? 's' : ''} as zip${sizeText ? ' (' + sizeText + ')' : ''}`;
</script>

<Popover text={$status ? `<strong>${$status}</strong>` : `<strong>${tooltip}</strong>`}>
  <span slot="trigger">
    <button class="control" on:click={doDownload}
            disabled={count === 0 || downloading}
            title={tooltip}>
      <iconify-icon icon="mdi:download" inline class:icon-spin={downloading}></iconify-icon> {label}
    </button>
  </span>
</Popover>
