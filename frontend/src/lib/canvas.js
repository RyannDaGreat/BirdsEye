/**
 * Pure canvas drawing functions for statistical visualizations.
 * All functions take a canvas 2D context and data, draw directly, return nothing.
 * No side effects beyond the canvas mutations.
 */

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
