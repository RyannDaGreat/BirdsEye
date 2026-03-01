<script>
  /**
   * Ternary filter button: cycles Any → Only → None → Any.
   *
   * Props:
   *   value: 'any' | 'only' | 'none'
   *   labelAny, labelOnly, labelNone: display text per state
   *   iconAny, iconOnly, iconNone: Iconify icon names per state
   *   title: tooltip text (optional)
   */
  import { createEventDispatcher } from 'svelte';

  export let value = 'any';
  export let labelAny = 'Any';
  export let labelOnly = 'Only';
  export let labelNone = 'None';
  export let iconAny = 'mdi:checkbox-blank-circle-outline';
  export let iconOnly = 'mdi:checkbox-marked-circle';
  export let iconNone = 'mdi:cancel';
  export let title = '';

  const dispatch = createEventDispatcher();

  const cycle = { any: 'only', only: 'none', none: 'any' };

  function onClick() {
    value = cycle[value] || 'any';
    dispatch('change', value);
  }

  $: currentIcon = value === 'only' ? iconOnly : value === 'none' ? iconNone : iconAny;
  $: currentLabel = value === 'only' ? labelOnly : value === 'none' ? labelNone : labelAny;
  $: active = value !== 'any';
</script>

<button class="control" class:active-toggle={active} on:click={onClick} {title}>
  <iconify-icon icon={currentIcon} inline></iconify-icon>
  {currentLabel}
</button>
