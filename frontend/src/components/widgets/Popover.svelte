<script>
  /**
   * Hover-triggered popover. Content is rendered into document.body
   * so it escapes all parent stacking contexts and overflow.
   */
  import { onMount, onDestroy } from 'svelte';

  export let text = '';

  let triggerEl;
  let portalEl;

  onMount(() => {
    portalEl = document.createElement('div');
    Object.assign(portalEl.style, {
      position: 'fixed',
      zIndex: 'var(--z-tooltip)',
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius)',
      padding: 'var(--space-md) var(--space-lg)',
      fontSize: 'var(--font-size-small)',
      color: 'var(--text)',
      width: '300px',
      whiteSpace: 'normal',
      wordWrap: 'break-word',
      lineHeight: 'var(--line-height)',
      boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
      pointerEvents: 'none',
      display: 'none',
    });
    document.body.appendChild(portalEl);
  });

  onDestroy(() => { if (portalEl) portalEl.remove(); });

  function show() {
    if (!triggerEl || !portalEl) return;
    const rect = triggerEl.getBoundingClientRect();
    portalEl.style.left = rect.left + 'px';
    portalEl.style.top = (rect.bottom + 4) + 'px';
    portalEl.innerHTML = text;
    portalEl.style.display = 'block';
  }

  function hide() {
    if (portalEl) portalEl.style.display = 'none';
  }
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<span class="popover-trigger" bind:this={triggerEl}
      on:mouseenter={show} on:mouseleave={hide}>
  <slot name="trigger" />
</span>

<style>
  .popover-trigger { cursor: help; display: inline-flex; }
</style>
