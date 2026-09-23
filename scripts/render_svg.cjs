#!/usr/bin/env node
// Render a pre-audited SVG with an already installed Sharp. No package installation.
const fs = require('node:fs');
const path = require('node:path');

async function main() {
  const [input, output, scaleArg = '2', sharpPath] = process.argv.slice(2);
  if (!input || !output) {
    throw new Error('Usage: node render_svg.cjs input.svg output.png [scale=2] [sharp-module-path]');
  }
  const scale = Number(scaleArg);
  if (!Number.isFinite(scale) || scale <= 0 || scale > 16) {
    throw new Error('Scale must be greater than 0 and no greater than 16');
  }
  if (path.resolve(input) === path.resolve(output) || path.extname(output).toLowerCase() !== '.png') {
    throw new Error('Output must be a distinct .png file');
  }
  let sharp;
  try { sharp = require(sharpPath ? path.resolve(sharpPath) : 'sharp'); }
  catch { throw new Error('Sharp not found. Supply its package directory, e.g. /path/to/node_modules/sharp, as the fourth argument.'); }
  const metadata = await sharp(input).metadata();
  if (metadata.format !== 'svg' || !metadata.width || !metadata.height) {
    throw new Error('Input must be an SVG with a finite canvas size');
  }
  // Base metadata respects explicit SVG units. Scale that raster size, not an assumed DPI.
  const width = Math.max(1, Math.round(metadata.width * scale));
  const height = Math.max(1, Math.round(metadata.height * scale));
  if (width * height > 100_000_000) throw new Error('Preview exceeds 100 million pixels');
  fs.mkdirSync(path.dirname(path.resolve(output)), {recursive: true});
  const result = await sharp(input, {density: 72 * scale})
    .resize(width, height, {fit: 'fill'}).png().toFile(output);
  process.stdout.write(JSON.stringify({file: path.resolve(output), width: result.width,
    height: result.height, bytes: result.size}) + '\n');
}
main().catch(error => { process.stderr.write(error.message + '\n'); process.exitCode = 1; });
