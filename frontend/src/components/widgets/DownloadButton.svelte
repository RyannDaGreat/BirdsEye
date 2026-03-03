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
    - Confirms via ConfirmModal when count exceeds threshold
    - Uses shared downloadSamples() from api.js
-->
<script>
  import { writable } from 'svelte/store';
  import { downloadSamples, fetchDownloadSize } from '../../lib/api.js';
  import { humanFilesize } from '../../lib/format.js';
  import { currentDataset } from '../../lib/stores.js';
  import Popover from './Popover.svelte';
  import ConfirmModal from './ConfirmModal.svelte';

  export let dataset = '';
  export let videoNames = [];
  export let artifact = null;
  export let compact = false;

  const CONFIRM_THRESHOLD = 100;
  const status = writable('');
  let sizeText = '';
  let sizeLoading = false;
  let errorText = '';
  let showConfirm = false;

  $: effectiveDataset = dataset || $currentDataset;
  $: count = videoNames.length;
  $: effectiveArtifact = artifact || null;
  $: if (count > 0) fetchSize(effectiveDataset, videoNames, effectiveArtifact);
  $: if (count === 0) { sizeText = ''; errorText = ''; }

  async function fetchSize(ds, names, art) {
    sizeLoading = true;
    sizeText = '';
    errorText = '';
    try {
      const { total_bytes } = await fetchDownloadSize(ds, names, art);
      sizeText = humanFilesize(total_bytes);
    } catch {
      sizeText = '';
    }
    sizeLoading = false;
  }

  function onClick() {
    if (count === 0 || $status) return;
    if (count > CONFIRM_THRESHOLD) {
      showConfirm = true;
    } else {
      doDownload();
    }
  }

  async function doDownload() {
    showConfirm = false;
    errorText = '';
    try {
      await downloadSamples(effectiveDataset, videoNames, effectiveArtifact, status);
    } catch (e) {
      errorText = e.message;
    }
  }

  $: downloading = !!$status;
  $: label = compact
    ? `${count}${sizeText ? ' · ' + sizeText : ''}`
    : `Download (${count})${sizeText ? ' · ' + sizeText : ''}`;
  $: tooltip = errorText
    ? errorText
    : $status
      ? $status
      : `Download ${count} ${effectiveArtifact || 'sample'}${count > 1 ? 's' : ''} as zip${sizeText ? ' (' + sizeText + ')' : ''}`;
  $: confirmMessage = `Download <strong>${count}</strong> ${effectiveArtifact || 'sample'}${count > 1 ? 's' : ''}${sizeText ? ' (' + sizeText + ')' : ''}?<br><span class="dim">This may take a while.</span>`;
</script>

<Popover text={errorText ? `<strong style="color:var(--error,#f44)">${errorText}</strong>` : $status ? `<strong>${$status}</strong>` : `<strong>${tooltip}</strong>`}>
  <span slot="trigger">
    <button class="control" class:error={!!errorText} on:click={onClick}
            disabled={count === 0 || downloading}
            title={tooltip}>
      <iconify-icon icon={errorText ? 'mdi:alert-circle-outline' : 'mdi:download'} inline class:icon-spin={downloading}></iconify-icon> {label}
    </button>
  </span>
</Popover>

<ConfirmModal show={showConfirm} title="Large Download"
  message={confirmMessage} confirmText="Download" cancelText="Cancel"
  on:confirm={doDownload} on:cancel={() => showConfirm = false} />

<style>
  .error { color: var(--error, #f44); }
</style>
