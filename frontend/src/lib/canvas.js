/**
 * Pure canvas drawing functions for statistical visualizations.
 * All functions take a canvas 2D context and data, draw directly, return nothing.
 * No side effects beyond the canvas mutations.
 */

/**
 * Find the tight bounding box of non-zero alpha pixels in a canvas.
 * Scans from each edge inward, stopping at the first opaque pixel.
 * Returns logical pixel coordinates (physical pixels ÷ dpr).
 * Pure function.
 *
 * @param {HTMLCanvasElement} canvas - source canvas to scan
 * @param {number} dpr - device pixel ratio used when rendering (physical = logical × dpr)
 * @returns {{x: number, y: number, w: number, h: number}} bounding box in logical pixels
 *
 * >>> // Conceptually: a 4×4 canvas with alpha only at (1,1) and (2,2)
 * >>> // findAlphaBounds(canvas, 1) → { x: 1, y: 1, w: 2, h: 2 }
 */
export function findAlphaBounds(canvas, dpr = 1) {
  const pw = canvas.width;
  const ph = canvas.height;
  const ctx = canvas.getContext('2d');
  const data = ctx.getImageData(0, 0, pw, ph).data;

  let minX = pw, maxX = -1, minY = ph, maxY = -1;

  // Scan top-to-bottom for minY
  for (let y = 0; y < ph && minY === ph; y++) {
    const row = y * pw * 4;
    for (let x = 0; x < pw; x++) {
      if (data[row + x * 4 + 3] > 0) { minY = y; break; }
    }
  }
  if (minY === ph) return { x: 0, y: 0, w: 0, h: 0 }; // fully transparent

  // Scan bottom-to-top for maxY
  for (let y = ph - 1; y >= minY && maxY === -1; y--) {
    const row = y * pw * 4;
    for (let x = 0; x < pw; x++) {
      if (data[row + x * 4 + 3] > 0) { maxY = y; break; }
    }
  }

  // Scan left-to-right for minX (within minY..maxY)
  for (let x = 0; x < pw && minX === pw; x++) {
    for (let y = minY; y <= maxY; y++) {
      if (data[(y * pw + x) * 4 + 3] > 0) { minX = x; break; }
    }
  }

  // Scan right-to-left for maxX
  for (let x = pw - 1; x >= minX && maxX === -1; x--) {
    for (let y = minY; y <= maxY; y++) {
      if (data[(y * pw + x) * 4 + 3] > 0) { maxX = x; break; }
    }
  }

  return {
    x: Math.floor(minX / dpr),
    y: Math.floor(minY / dpr),
    w: Math.ceil((maxX - minX + 1) / dpr),
    h: Math.ceil((maxY - minY + 1) / dpr),
  };
}

/**
 * Set up a canvas for high-DPI rendering with 2x supersampling.
 * Canvas pixel dimensions = CSS size × devicePixelRatio × 2 for extra sharpness
 * when zooming in with the browser.
 * Pure function (mutates only the provided canvas).
 *
 * @param {HTMLCanvasElement} canvas
 * @returns {{ctx: CanvasRenderingContext2D, w: number, h: number}} logical width/height
 */
export function setupCanvas(canvas) {
  const dpr = (window.devicePixelRatio || 1) * 2;
  const rect = canvas.getBoundingClientRect();
  const w = Math.floor(rect.width);
  const h = Math.floor(rect.height);
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  return { ctx, w, h };
}

/**
 * Draw a scatter plot on a canvas context.
 * Normalizes x/y values to fill the canvas area with padding.
 * Pure function (mutates only the provided canvas context).
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {number[]} xValues
 * @param {number[]} yValues
 * @param {number} width - logical canvas width
 * @param {number} height - logical canvas height
 * @param {string} color - CSS color for dots
 * @param {number} opacity - dot opacity (0-1)
 * @param {number} dotRadius - radius of each dot in logical pixels
 */
export function drawScatter(ctx, xValues, yValues, width, height, color = '#4a9eff', opacity = 0.3, dotRadius = 0.75) {
  if (xValues.length === 0 || yValues.length === 0) return;
  const n = Math.min(xValues.length, yValues.length);
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const yMin = Math.min(...yValues);
  const yMax = Math.max(...yValues);
  const xRange = xMax - xMin || 1;
  const yRange = yMax - yMin || 1;
  const pad = 2;
  const drawW = width - pad * 2;
  const drawH = height - pad * 2;

  ctx.globalAlpha = opacity;
  ctx.fillStyle = color;
  for (let i = 0; i < n; i++) {
    const px = pad + ((xValues[i] - xMin) / xRange) * drawW;
    const py = height - pad - ((yValues[i] - yMin) / yRange) * drawH;
    ctx.beginPath();
    ctx.arc(px, py, dotRadius, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}

/**
 * Draw a histogram on a canvas context.
 * Bins values and draws vertical bars filling the canvas. Bars touch with no gap.
 * Pure function (mutates only the provided canvas context).
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {number[]} values
 * @param {number} bins - number of histogram bins
 * @param {number} width - logical canvas width
 * @param {number} height - logical canvas height
 * @param {string} color - CSS color for bars
 */
export function drawHistogram(ctx, values, bins, width, height, color = '#4a9eff') {
  if (values.length === 0) return;
  const vMin = Math.min(...values);
  const vMax = Math.max(...values);
  const range = vMax - vMin || 1;

  const counts = new Array(bins).fill(0);
  for (const v of values) {
    const idx = Math.min(bins - 1, Math.max(0, Math.floor(((v - vMin) / range) * bins)));
    counts[idx]++;
  }

  const maxCount = Math.max(...counts);
  if (maxCount === 0) return;

  ctx.fillStyle = color;
  ctx.globalAlpha = 0.6;
  for (let i = 0; i < bins; i++) {
    const x = (i / bins) * width;
    const nextX = ((i + 1) / bins) * width;
    const barW = Math.ceil(nextX - x);
    const barH = (counts[i] / maxCount) * height;
    ctx.fillRect(x, height - barH, barW, barH);
  }
  ctx.globalAlpha = 1;
}
