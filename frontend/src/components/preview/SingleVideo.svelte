<!--
  Generic: one video with controls, full width.
  Args: file (filename in sample dir) OR url (direct URL)
-->
<script>
  import { currentDataset } from '../../lib/stores.js';

  export let videoName = '';
  export let args = {};

  $: file = args.file || '';
  $: url = args.url || (file ? `/thumbnails/${$currentDataset}/${videoName}/${file}` : '');
</script>

{#if url}
  <video src={url} loop autoplay muted controls>
  </video>
{/if}

<style>
  video { width: 100%; border-radius: var(--radius); background: var(--black); display: block; }
</style>
