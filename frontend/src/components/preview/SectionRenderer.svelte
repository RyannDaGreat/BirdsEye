<!--
  Renders a preview section by type. Maps type strings to renderer components.
  Adding a new renderer = import it + add to the renderers map.
-->
<script>
  import PreviewSection from './PreviewSection.svelte';
  import SideBySideImages from './SideBySideImages.svelte';
  import SideBySideVideos from './SideBySideVideos.svelte';
  import SingleImage from './SingleImage.svelte';
  import SingleVideo from './SingleVideo.svelte';

  export let section = {};
  export let videoName = '';

  const renderers = {
    side_by_side_images: SideBySideImages,
    side_by_side_videos: SideBySideVideos,
    single_image: SingleImage,
    single_video: SingleVideo,
  };

  $: component = renderers[section.type] || null;
</script>

{#if component}
  <PreviewSection label={section.label} defaultOpen={section.priority <= 30}>
    <svelte:component this={component} {videoName} args={section.args || {}} />
  </PreviewSection>
{/if}
