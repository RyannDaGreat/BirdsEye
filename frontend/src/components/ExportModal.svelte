<script>
  import { showExport } from '../lib/stores.js';

  export let text = '';

  let copyLabel = 'Copy to Clipboard';

  function copy() {
    navigator.clipboard.writeText(text);
    copyLabel = 'Copied!';
    setTimeout(() => { copyLabel = 'Copy to Clipboard'; }, 1500);
  }

  function saveAsFile() {
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'birdseye_export.txt';
    a.click();
    URL.revokeObjectURL(url);
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
    <div class="modal">
      <h2>Export Video Names</h2>
      <textarea readonly>{text}</textarea>
      <div class="buttons">
        <button class="control" on:click={copy} title="Copy all video names to clipboard">{copyLabel}</button>
        <button class="control" on:click={saveAsFile} title="Save video names as a .txt file"><iconify-icon icon="mdi:content-save" inline></iconify-icon> Save as .txt</button>
        <button class="control" on:click={close} title="Close export dialog">Close</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-overlay {
    position: fixed; inset: 0; background: rgba(0, 0, 0, 0.7);
    z-index: 1000; display: flex; align-items: center; justify-content: center;
  }
  .modal {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: var(--space-3xl);
    max-width: 600px; width: 90%; max-height: 80vh;
    display: flex; flex-direction: column; gap: var(--space-lg);
  }
  h2 { font-size: var(--font-size-base); color: var(--accent); }
  textarea {
    background: var(--bg); border: 1px solid var(--border);
    color: var(--text); font-family: var(--font); font-size: var(--font-size-control);
    padding: var(--space-lg); border-radius: var(--radius); resize: vertical; min-height: 200px; outline: none;
  }
  .buttons { display: flex; gap: var(--space-md); justify-content: flex-end; }
</style>
