<!--
  Generic: N images side by side with labels.
  Args: files (filenames in sample dir), labels (display names)
-->
<script>
  import { currentDataset } from '../../lib/stores.js';
  import SafeImage from '../widgets/SafeImage.svelte';

  export let videoName = '';
  export let args = {};

  $: files = args.files || [];
  $: labels = args.labels || files;
</script>

<div class="grid">
  {#each files as file, i}
    <div class="cell">
      {#if labels[i]}<div class="label">{labels[i]}</div>{/if}
      <SafeImage src="/thumbnails/{$currentDataset}/{videoName}/{file}" alt={labels[i] || file} />
    </div>
  {/each}
</div>

<style>
  .grid { display: flex; gap: var(--space-sm); }
  .cell { flex: 1; min-width: 0; text-align: center; }
  .cell :global(img) { width: 100%; border-radius: var(--radius); }
  .label { font-size: var(--font-size-xs); color: var(--text-dim); margin-bottom: var(--space-xs); }
</style>
