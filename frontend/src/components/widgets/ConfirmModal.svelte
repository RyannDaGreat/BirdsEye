<!--
  Reusable confirmation modal. Uses shared .modal-* classes from app.css.

  Props:
    show        — boolean, controls visibility
    title       — header text (default "Confirm")
    message     — body text (supports HTML)
    confirmText — confirm button label (default "OK")
    cancelText  — cancel button label (default "Cancel")

  Events:
    on:confirm  — user clicked confirm
    on:cancel   — user clicked cancel, X, overlay, or Escape
-->
<script>
  import { createEventDispatcher } from 'svelte';

  export let show = false;
  export let title = 'Confirm';
  export let message = '';
  export let confirmText = 'OK';
  export let cancelText = 'Cancel';

  const dispatch = createEventDispatcher();

  function confirm() { dispatch('confirm'); }
  function cancel() { dispatch('cancel'); }

  function onOverlayClick(e) {
    if (e.target === e.currentTarget) cancel();
  }

  function onKeydown(e) {
    if (show && e.key === 'Escape') cancel();
  }
</script>

<svelte:window on:keydown={onKeydown} />

{#if show}
  <!-- svelte-ignore a11y-no-static-element-interactions a11y-click-events-have-key-events -->
  <div class="modal-overlay" on:click={onOverlayClick}>
    <div class="modal-box confirm-modal">
      <div class="modal-header">
        <h2><iconify-icon icon="mdi:alert-circle-outline" inline></iconify-icon> {title}</h2>
        <button class="modal-close" on:click={cancel} title="Cancel">
          <iconify-icon icon="mdi:close" inline></iconify-icon>
        </button>
      </div>
      <div class="modal-body">{@html message}</div>
      <div class="modal-footer">
        <button class="control" on:click={cancel}>{cancelText}</button>
        <button class="control" on:click={confirm}>{confirmText}</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .confirm-modal { max-width: 450px; width: 90vw; }
</style>
