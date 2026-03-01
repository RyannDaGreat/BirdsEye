<script>
  import { currentResults, loading, errorMsg } from '../lib/stores.js';
  import VideoCard from './VideoCard.svelte';
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher();

  function onToggle(e) { dispatch('toggle', e.detail); }
  function onDetail(e) { dispatch('detail', e.detail); }
  function onFavorite(e) { dispatch('favorite', e.detail); }
</script>

<div class="main">
  {#if $loading}
    <div class="loading"><div class="spinner"></div>Loading...</div>
  {:else if $errorMsg}
    <div class="loading"><span class="error">{$errorMsg}</span></div>
  {:else}
    <div class="grid">
      {#each $currentResults as item (item.video_name)}
        <VideoCard {item} on:toggle={onToggle} on:detail={onDetail} on:favorite={onFavorite} />
      {/each}
    </div>
  {/if}
</div>

<style>
  .main { flex: 1; overflow-y: auto; padding: var(--space-lg); min-width: 0; background: var(--bg); }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: var(--space-md);
  }
  .loading {
    display: flex; align-items: center; justify-content: center;
    padding: 60px; color: var(--text-dim); font-size: var(--font-size-base);
  }
  .error { color: var(--selected); }
</style>
