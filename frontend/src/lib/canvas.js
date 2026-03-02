/**
 * Pure canvas drawing functions for statistical visualizations.
 * All functions take a canvas 2D context and data, draw directly, return nothing.
 * No side effects beyond the canvas mutations.
 */

/**
 * Draw a scatter plot on a canvas context.
 * Normalizes x/y values to fill the canvas area.
 * Pure function (mutates only the provided canvas context).
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {number[]} xValues
 * @param {number[]} yValues
 * @param {number} width - canvas width in pixels
 * @param {number} height - canvas height in pixels
 * @param {string} color - CSS color for dots
 * @param {number} opacity - dot opacity (0-1)
 */
export function drawScatter(ctx, xValues, yValues, width, height, color = '#4a9eff', opacity = 0.3) {
  if (xValues.length === 0 || yValues.length === 0) return;
  const n = Math.min(xValues.length, yValues.length);
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const yMin = Math.min(...yValues);
  const yMax = Math.max(...yValues);
  const xRange = xMax - xMin || 1;
  const yRange = yMax - yMin || 1;
  const pad = 4;
  const drawW = width - pad * 2;
  const drawH = height - pad * 2;

  ctx.globalAlpha = opacity;
  ctx.fillStyle = color;
  for (let i = 0; i < n; i++) {
    const px = pad + ((xValues[i] - xMin) / xRange) * drawW;
    const py = height - pad - ((yValues[i] - yMin) / yRange) * drawH;
    ctx.beginPath();
    ctx.arc(px, py, 1.5, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}

/**
 * Draw a histogram on a canvas context.
 * Bins values and draws vertical bars filling the canvas.
 * Pure function (mutates only the provided canvas context).
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {number[]} values
 * @param {number} bins - number of histogram bins
 * @param {number} width - canvas width in pixels
 * @param {number} height - canvas height in pixels
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

  const barW = width / bins;
  const pad = 2;
  ctx.fillStyle = color;
  ctx.globalAlpha = 0.6;
  for (let i = 0; i < bins; i++) {
    const barH = (counts[i] / maxCount) * (height - pad);
    ctx.fillRect(i * barW, height - barH, barW - 1, barH);
  }
  ctx.globalAlpha = 1;
}
