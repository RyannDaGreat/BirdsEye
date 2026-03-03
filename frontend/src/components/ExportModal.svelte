<script>
  import { showExport, fieldInfo, currentDataset } from '../lib/stores.js';
  import ModeTabRow from './widgets/ModeTabRow.svelte';
  import DownloadButton from './widgets/DownloadButton.svelte';

  export let names = [];
  export let paths = [];
  export let loading = false;

  let contentMode = 'names';
  let formatMode = 'lines';
  let artifact = 'Folder';
  let copyLabel = 'Copy';

  const contentOptions = [
    { value: 'names', label: 'Names' },
    { value: 'paths', label: 'Paths' },
  ];
  const formatOptions = [
    { value: 'lines', label: 'Lines' },
    { value: 'json',  label: 'JSON' },
  ];

  $: artifactOptions = buildArtifactOptions($fieldInfo);

  function buildArtifactOptions(info) {
    const opts = ['Folder', 'origins.json', 'video.mp4'];
    const imageArts = info.image_artifacts || {};
    const dataArts = info.data_artifacts || {};
    for (const fn of Object.keys(imageArts)) {
      if (!opts.includes(fn)) opts.push(fn);
    }
    for (const fn of Object.keys(dataArts)) {
      if (!opts.includes(fn)) opts.push(fn);
    }
    return opts;
  }

  $: items = contentMode === 'names'
    ? names
    : paths.map(p => artifact === 'Folder' ? p : `${p}/${artifact}`);

  $: displayText = formatMode === 'lines'
    ? items.join('\n')
    : JSON.stringify(items, null, 2);

  $: downloadArtifact = (contentMode === 'paths' && artifact !== 'Folder') ? artifact : null;

  $: fileExt = formatMode === 'json' ? '.json' : '.txt';
  $: mimeType = formatMode === 'json' ? 'application/json' : 'text/plain';

  function copy() {
    navigator.clipboard.writeText(displayText);
    copyLabel = 'Copied!';
    setTimeout(() => { copyLabel = 'Copy'; }, 1500);
  }

  async function saveAsFile() {
    const blob = new Blob([displayText], { type: mimeType });
    const filename = `birdseye_export${fileExt}`;
    if (window.showSaveFilePicker) {
      const handle = await window.showSaveFilePicker({
        suggestedName: filename,
        types: [{
          description: formatMode === 'json' ? 'JSON files' : 'Text files',
          accept: { [mimeType]: [fileExt] },
        }],
      });
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
    } else {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    }
  }

  function close() { $showExport = false; }

  function onOverlayClick(e) {
    if (e.target === e.currentTarget) close();
  }

  function onKeydown(e) {
    if (e.key === 'Escape') close();
  }
</script>

<svelte:window on:keydown={onKeydown} />

{#if $showExport}
  <!-- svelte-ignore a11y-no-static-element-interactions a11y-click-events-have-key-events -->
  <div class="modal-overlay" on:click={onOverlayClick}>
    <div class="modal-box export-modal">
      <!-- HEADER -->
      <div class="modal-header">
        <h2><iconify-icon icon="mdi:export" inline></iconify-icon> Export</h2>
        <button class="modal-close" on:click={close} title="Close">
          <iconify-icon icon="mdi:close" inline></iconify-icon>
        </button>
      </div>

      <!-- CONTROLS -->
      <div class="controls">
        <div class="control-row">
          <span class="control-label">Content</span>
          <ModeTabRow options={contentOptions} bind:value={contentMode} compact />
          {#if contentMode === 'paths'}
            <span class="control-label artifact-label">Artifact</span>
            <select class="artifact-select" bind:value={artifact}>
              {#each artifactOptions as opt}
                <option value={opt}>{opt}</option>
              {/each}
            </select>
          {/if}
        </div>
        <div class="control-row">
          <span class="control-label">Format</span>
          <ModeTabRow options={formatOptions} bind:value={formatMode} compact />
        </div>
      </div>

      <!-- CONTENT -->
      <div class="content-area">
        <textarea readonly>{displayText}</textarea>
        {#if loading}
          <div class="loading-overlay">
            <div class="spinner"></div>
          </div>
        {/if}
      </div>

      <!-- FOOTER -->
      <div class="modal-footer">
        <DownloadButton dataset={$currentDataset} videoNames={names} artifact={downloadArtifact} compact />
        <button class="control" on:click={copy} title="Copy to clipboard">
          <iconify-icon icon="mdi:content-copy" inline></iconify-icon> {copyLabel}
        </button>
        <button class="control" on:click={saveAsFile} title="Save as file">
          <iconify-icon icon="mdi:content-save" inline></iconify-icon> Save as {fileExt}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  /* Export-specific sizing (shared modal classes from app.css handle the rest) */
  .export-modal {
    width: 80vw; height: 85vh;
  }

  /* CONTROLS */
  .controls {
    display: flex; flex-direction: column; gap: var(--space-sm);
    flex-shrink: 0;
  }
  .control-row {
    display: flex; align-items: center; gap: var(--space-md);
  }
  .control-label {
    font-size: var(--font-size-xs); color: var(--text-dim);
    min-width: 50px; flex-shrink: 0;
  }
  .artifact-label { margin-left: var(--space-lg); }
  .artifact-select {
    background: var(--bg); border: 1px solid var(--border);
    color: var(--text); font-family: var(--font); font-size: var(--font-size-xs);
    padding: var(--space-xs) var(--space-sm); border-radius: var(--radius);
    outline: none;
  }

  /* CONTENT */
  .content-area {
    flex: 1; min-height: 0; position: relative;
    display: flex; flex-direction: column;
  }
  textarea {
    background: var(--bg); border: 1px solid var(--border);
    color: var(--text); font-family: var(--font); font-size: var(--font-size-control);
    padding: var(--space-lg); border-radius: var(--radius);
    resize: none; flex: 1; min-height: 0; outline: none;
  }
  .loading-overlay {
    position: absolute; inset: 0;
    background: var(--modal-loading-bg);
    display: flex; align-items: center; justify-content: center;
    border-radius: var(--radius);
  }
</style>
