<script>
  /**
   * Image that shows an error message when it fails to load or has no src.
   * Props: src, alt, aspectRatio (default "16/9")
   */
  export let src = '';
  export let alt = '';
  export let aspectRatio = '16/9';

  let failed = false;

  function onError() { failed = true; }

  $: hasSrc = src && src.length > 0;
  $: showError = !hasSrc || failed;
  $: errorText = !hasSrc ? 'no image' : `failed: ${src.split('/').pop()}`;
</script>

{#if showError}
  <div class="img-error" style="aspect-ratio: {aspectRatio};">{errorText}</div>
{:else}
  <img {src} {alt} loading="lazy" on:error={onError} />
{/if}

<style>
  img { width: 100%; border-radius: var(--radius); display: block; }
  .img-error {
    width: 100%; background: var(--bg); border-radius: var(--radius);
    display: flex; align-items: center; justify-content: center;
    font-size: var(--font-size-xxs); color: var(--selected-dim);
  }
</style>
