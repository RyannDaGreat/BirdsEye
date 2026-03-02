import { writable, derived } from 'svelte/store';

// --- Core state ---
export const currentDataset = writable('pexels');
export const currentMode = writable('fuzzy');
export const currentSort = writable('');
export const searchQuery = writable('');
export const currentResults = writable([]);
export const selectedVideos = writable(new Set());
export const datasets = writable({});
export const metadataStats = writable({});
export const histogramData = writable({});
export const fieldInfo = writable({ fields: {}, image_outputs: {} });
export const appConfig = writable({ sprite_cols: 5, sprite_rows: 5, sprite_frames: 25 });
export const embeddingModels = writable({});  // {prefix: {name, description, dim}}
export const logScale = writable(true);
export const hoveredItem = writable(null); // video item being hovered in grid
export const loading = writable(false);
export const errorMsg = writable('');
export const errorHint = writable('');

// --- Panel visibility ---
export const showFilters = writable(false);
export const showStats = writable(false);
export const showHelp = writable(false);
export const showExport = writable(false);

// --- Ternary filters ('any' | 'only' | 'none') ---
export const thumbFilter = writable('any');
export const favFilter = writable('any');

// --- Favorites ---
export const favorites = writable(new Set());

// --- Detail panel ---
export const detailData = writable(null);  // full video_info response
export const detailWidth = writable(380);

// --- Filters ---
export const filters = writable({});

// --- Pagination ---
export const pageSize = writable(200);
export const currentPage = writable(1);
export const totalResults = writable(0); // server-reported total (across all pages)

// --- Derived ---
export const datasetInfo = derived(
  [datasets, currentDataset],
  ([$datasets, $currentDataset]) => $datasets[$currentDataset] || { count: 0 }
);
