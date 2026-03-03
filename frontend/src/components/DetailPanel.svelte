<script>
  import { detailData, currentDataset, detailWidth, searchQuery, favorites, downloadStatus } from '../lib/stores.js';
  import { formatNumber, collectVideoFields, highlightTerms } from '../lib/format.js';
  import { fieldLabel, fieldTooltip } from '../lib/fields.js';
  import { downloadSamples } from '../lib/api.js';
  import FieldBar from './widgets/FieldBar.svelte';
  import PreviewSection from './preview/PreviewSection.svelte';
  import SectionRenderer from './preview/SectionRenderer.svelte';
  import { onMount } from 'svelte';

  let previewSections = [];
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher();

  let dragging = false;
  let startX = 0;
  let startWidth = 0;

  function close() {
    $detailData = null;
  }

  function onKeydown(e) {
    if (e.key === 'Escape') close();
  }

  function startResize(e) {
    dragging = true;
    startX = e.clientX;
    startWidth = $detailWidth;
    document.body.style.cursor = 'ew-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  }

  function onMouseMove(e) {
    if (!dragging) return;
    const newW = Math.max(280, Math.min(window.innerWidth * 0.8, startWidth + startX - e.clientX));
    $detailWidth = newW;
  }

  function onMouseUp() {
    if (!dragging) return;
    dragging = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  }

  function toggleFav() {
    if ($detailData) dispatch('favorite', $detailData.video_name);
  }

  async function downloadSingle() {
    if ($detailData) await downloadSamples($currentDataset, [$detailData.video_name]);
  }

  onMount(async () => {
    try {
      const resp = await fetch('/api/preview_sections');
      if (resp.ok) previewSections = await resp.json();
    } catch (e) { console.warn('Failed to load preview sections:', e); }
  });

  $: visible = $detailData !== null;
  $: allFields = visible ? collectVideoFields($detailData) : [];
  $: isFav = visible && $favorites.has($detailData.video_name);
</script>

<svelte:window on:mousemove={onMouseMove} on:mouseup={onMouseUp} on:keydown={onKeydown} />

{#if visible}
  <div class="detail-panel" style="width: {$detailWidth}px;">
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="resize-handle" class:dragging on:mousedown={startResize} title="Drag to resize panel"></div>
    <button class="close-btn" on:click={close} title="Close detail panel (Escape)">&times;</button>

    <div class="detail-name"><span class="dataset-prefix">{$currentDataset}:</span><span class="video-title">{$detailData.video_name}</span></div>

    <!-- Preview Button Bar (always visible, not collapsible) -->
    <div class="detail-toolbar">
      <button class="toolbar-btn" class:fav-active={isFav} on:click={toggleFav}
              title={isFav ? 'Remove from favorites' : 'Add to favorites'}>
        <iconify-icon icon={isFav ? 'mdi:heart' : 'mdi:heart-outline'} inline></iconify-icon>
        {isFav ? 'Favorited' : 'Favorite'}
      </button>
      <button class="toolbar-btn" on:click={downloadSingle} disabled={!!$downloadStatus}
              title={$downloadStatus || 'Download this sample\'s files as a zip'}>
        <iconify-icon icon="mdi:download" inline class:icon-spin={!!$downloadStatus}></iconify-icon>
        {$downloadStatus ? 'Downloading...' : 'Download'}
      </button>
    </div>

    <PreviewSection label="Video" defaultOpen={true}>
      <div class="video-container">
        <video src="/api/video/{$currentDataset}/{$detailData.video_name}"
               loop autoplay muted controls>
        </video>
      </div>
    </PreviewSection>

    <PreviewSection label="Fields" defaultOpen={true}>
      <div class="metadata">
        {#each allFields as { key, value }}
          <FieldBar
            label={fieldLabel(key)}
            value={formatNumber(value)}
            tooltip={fieldTooltip(key)}
            fieldKey={key}
          />
        {/each}
      </div>
    </PreviewSection>

    <PreviewSection label="Caption" defaultOpen={true}>
      <div class="detail-caption">{@html highlightTerms($detailData.caption || '', $searchQuery)}</div>
    </PreviewSection>

    <!-- Plugin-declared preview sections (accordion) -->
    {#each previewSections as section}
      <SectionRenderer {section} videoName={$detailData.video_name} />
    {/each}

    <div class="detail-path">{$detailData.sample_path || $detailData.source_path || ''}</div>
  </div>
{/if}

<style>
  .detail-panel {
    position: relative;
    flex-shrink: 0;
    min-width: 280px; max-width: 80vw;
    background: var(--surface);
    border-left: 1px solid var(--border);
    display: flex; flex-direction: column;
    overflow-y: auto; padding: var(--space-2xl);
  }

  .resize-handle {
    position: absolute; left: 0; top: 0; bottom: 0; width: var(--resize-handle-size);
    cursor: ew-resize; background: transparent; z-index: 10; transition: background 0.15s;
  }
  .resize-handle:hover, .resize-handle.dragging { background: var(--accent); }

  .close-btn {
    position: absolute; top: var(--space-lg); right: var(--space-lg);
    background: none; border: none; color: var(--text-dim);
    font-size: var(--spinner-size); cursor: pointer;
  }

  .detail-name { font-size: var(--space-xl); color: var(--accent); margin-bottom: var(--space-md); }
  .dataset-prefix { font-weight: 400; color: var(--text-dim); }
  .video-title { font-weight: 700; }

  .video-container { margin-bottom: var(--space-sm); }
  video { width: 100%; aspect-ratio: 16/9; border-radius: var(--radius); background: var(--black); display: block; }

  .detail-toolbar {
    display: flex; gap: var(--space-md); margin-bottom: var(--space-md);
  }
  .toolbar-btn {
    display: flex; align-items: center; gap: var(--space-xs);
    background: none; border: 1px solid var(--border); border-radius: var(--radius);
    color: var(--text-dim); font-family: var(--font); font-size: var(--font-size-control);
    padding: var(--space-xs) var(--space-md); cursor: pointer; transition: all 0.15s;
  }
  .toolbar-btn:hover { color: var(--text); border-color: var(--text-dim); }
  .toolbar-btn.fav-active { color: #e74c3c; border-color: #e74c3c; }

  .metadata { display: flex; gap: var(--space-sm); flex-wrap: wrap; margin-top: var(--space-md); margin-bottom: var(--space-md); }

  /* Preview sections rendered by SectionRenderer */

  .detail-caption { font-size: var(--font-size-control); line-height: 1.6; color: var(--text); }
  .detail-path { font-size: var(--font-size-xs); color: var(--text-dim); margin-top: var(--space-lg); word-break: break-all; }
</style>
