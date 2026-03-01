<script>
  import { currentDataset, selectedVideos, currentSort, searchQuery, appConfig, hoveredItem, favorites } from '../lib/stores.js';
  import { getNestedValue } from '../lib/sort.js';
  import { fieldLabel } from '../lib/fields.js';
  import { formatNumber, parseSortKey, spritePosition, mouseToFrameIndex, truncate, highlightTerms } from '../lib/format.js';
  import { createEventDispatcher, onMount } from 'svelte';

  export let item;

  const dispatch = createEventDispatcher();

  let spriteLoaded = false;
  let hovering = false;
  let hoverProgress = 0; // 0-1 fraction for progress bar
  let useSprite = false;

  $: isSelected = $selectedVideos.has(item.video_name);
  $: middleUrl = `/thumbnails/${$currentDataset}/${item.video_name}/thumb_middle.jpg`;
  $: firstUrl = `/thumbnails/${$currentDataset}/${item.video_name}/thumb_first.jpg`;
  $: lastUrl = `/thumbnails/${$currentDataset}/${item.video_name}/thumb_last.jpg`;
  $: spriteUrl = `/thumbnails/${$currentDataset}/${item.video_name}/sprite.jpg`;
  $: spriteBgSize = `${$appConfig.sprite_cols * 100}% ${$appConfig.sprite_rows * 100}%`;

  // Sort badge
  $: ({ key: sortKey } = parseSortKey($currentSort));
  $: sortVal = sortKey ? getNestedValue(item, sortKey) : undefined;
  $: badgeText = sortKey && sortVal !== undefined
    ? formatNumber(sortVal)
    : (item.score !== undefined ? formatNumber(item.score * 100, 1) : '');
  $: badgeTitle = sortKey ? fieldLabel(sortKey) : (item.score !== undefined ? 'Similarity score' : '');

  let hoverFrame = 'middle';
  $: currentSrc = hoverFrame === 'first' ? firstUrl : hoverFrame === 'last' ? lastUrl : middleUrl;

  onMount(() => {
    const probe = new Image();
    probe.onload = () => { spriteLoaded = true; };
    probe.onerror = () => { spriteLoaded = false; };
    probe.src = spriteUrl;
  });

  let spritePos = '0% 50%';

  function onMouseEnter() {
    hovering = true;
    if (spriteLoaded) {
      useSprite = true;
      spritePos = spritePosition(0);
      hoverProgress = 0;
    } else {
      hoverFrame = 'first';
    }
  }

  function onMouseLeave() {
    hovering = false;
    useSprite = false;
    hoverFrame = 'middle';
    hoverProgress = 0;
  }

  function onMouseMove(e) {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    hoverProgress = x;

    if (spriteLoaded && useSprite) {
      const fi = mouseToFrameIndex(x, $appConfig.sprite_frames);
      spritePos = spritePosition(fi, $appConfig.sprite_cols, $appConfig.sprite_rows);
    } else {
      if (x < 0.33) { hoverFrame = 'first'; }
      else if (x < 0.66) { hoverFrame = 'middle'; }
      else { hoverFrame = 'last'; }
    }
  }

  $: isFav = $favorites.has(item.video_name);

  function onClick(e) { e.preventDefault(); dispatch('toggle', item.video_name); }
  function onDblClick(e) { e.preventDefault(); dispatch('detail', item); }
  function onContext(e) { e.preventDefault(); dispatch('toggle', item.video_name); }
  function onFavClick(e) { e.stopPropagation(); dispatch('favorite', item.video_name); }
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="card" class:selected={isSelected}
     on:click={onClick} on:dblclick={onDblClick} on:contextmenu={onContext}
     on:mouseenter={() => $hoveredItem = item} on:mouseleave={() => $hoveredItem = null}>
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="thumb-container"
       on:mouseenter={onMouseEnter} on:mouseleave={onMouseLeave} on:mousemove={onMouseMove}>
    {#if useSprite}
      <div class="thumb-sprite" style="background-image: url({spriteUrl}); background-position: {spritePos}; background-size: {spriteBgSize};"></div>
    {:else}
      <img src={currentSrc} loading="lazy" alt=""
           on:error={(e) => { e.target.style.display = 'none'; e.target.parentNode.insertAdjacentHTML('beforeend', '<div style=\"position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--selected-dim);font-size:var(--font-size-xxs);background:var(--bg);\">failed to load</div>'); }} />
    {/if}
    {#if hovering}
      <div class="progress-bar"><div class="progress-fill" style="width: {hoverProgress * 100}%"></div></div>
    {/if}
    {#if badgeText}
      <div class="score-badge" title={badgeTitle}>{badgeText}</div>
    {/if}
    <div class="select-check" class:checked={isSelected}>{isSelected ? '\u2713' : ''}</div>
    <button class="fav-btn" class:fav-active={isFav} on:click={onFavClick}
            title={isFav ? 'Remove from favorites' : 'Add to favorites'}>
      <iconify-icon icon={isFav ? 'mdi:heart' : 'mdi:heart-outline'} inline></iconify-icon>
    </button>
  </div>
  <div class="card-info">
    <div class="video-name">{item.video_name}</div>
    <div class="caption-preview">{@html highlightTerms(truncate(item.caption), $searchQuery)}</div>
  </div>
</div>

<style>
  .card {
    background: var(--surface); border: 2px solid transparent;
    border-radius: var(--radius); overflow: hidden;
    cursor: pointer; transition: all 0.15s; position: relative;
  }
  .card:hover { border-color: var(--accent); }
  .card.selected { border-color: var(--selected); box-shadow: 0 0 var(--space-lg) rgba(255, 107, 53, 0.3); }

  .thumb-container {
    position: relative; width: 100%; aspect-ratio: 16/9;
    background: var(--black); overflow: hidden;
  }
  .thumb-sprite {
    width: 100%; height: 100%;
    background-repeat: no-repeat;
    background-color: var(--surface2);
  }
  img {
    width: 100%; height: 100%; object-fit: contain;
    background: var(--surface2);
  }

  .progress-bar {
    position: absolute; bottom: 0; left: 0; right: 0; height: 2px;
    background: rgba(0,0,0,0.5); pointer-events: none;
  }
  .progress-fill {
    height: 100%; background: #fff; transition: none;
  }
  .score-badge {
    position: absolute; top: var(--space-sm); left: var(--space-sm);
    background: rgba(74,158,255,0.85); color: #fff;
    padding: 1px var(--space-md); border-radius: var(--radius-xs);
    font-size: var(--font-size-xs); font-weight: 600; pointer-events: none;
  }
  .select-check {
    position: absolute; bottom: var(--space-sm); right: var(--space-sm);
    width: var(--select-check-size); height: var(--select-check-size); border-radius: 50%;
    border: 2px solid rgba(255,255,255,0.4);
    display: flex; align-items: center; justify-content: center;
    font-size: var(--font-size-control); pointer-events: none; transition: all 0.15s;
  }
  .select-check.checked { background: var(--selected); border-color: var(--selected); color: #fff; }

  .fav-btn {
    position: absolute; top: var(--space-sm); right: var(--space-sm);
    background: rgba(0,0,0,0.5); border: none; border-radius: 50%;
    width: 22px; height: 22px; display: flex; align-items: center; justify-content: center;
    color: rgba(255,255,255,0.6); font-size: 14px; cursor: pointer;
    transition: all 0.15s; opacity: 0;
  }
  .thumb-container:hover .fav-btn { opacity: 1; }
  .fav-btn.fav-active { opacity: 1; color: #e74c3c; background: rgba(0,0,0,0.7); }
  .fav-btn:hover { color: #e74c3c; background: rgba(0,0,0,0.7); }

  .card-info { padding: var(--space-md); }
  .video-name { font-weight: 600; font-size: var(--font-size-small); color: var(--accent); margin-bottom: var(--space-xs); }
  .caption-preview {
    font-size: var(--font-size-xs); color: var(--text-dim);
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden; line-height: 1.4;
  }
</style>
