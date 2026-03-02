<!--
  Generic: one image, full width.
  Args: file (filename in sample dir)
-->
<script>
  import { currentDataset } from '../../lib/stores.js';
  import SafeImage from '../widgets/SafeImage.svelte';

  export let videoName = '';
  export let args = {};

  $: file = args.file || '';
</script>

{#if file}
  <SafeImage src="/thumbnails/{$currentDataset}/{videoName}/{file}" alt={file} />
{/if}

<style>
  :global(.preview-section .single-img img) { width: 100%; border-radius: var(--radius); }
</style>
