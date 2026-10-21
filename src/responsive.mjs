/**
 * Responsive generator for seven semantic templates, invoked by --mode responsive. It
 * reconstructs layouts rather than preserving original coordinates/styles.
 *
 * @module responsive
 */
import fs from 'node:fs';
import path from 'node:path';
import { dependency } from './dependencies.mjs';
import { configure, merge } from './theme.mjs';
import { Canvas, root } from './components.mjs';
import { contents, source } from './content.mjs';
import { registerMasters, renderTemplate } from './templates.mjs';

/**
 * Prepare reader-compatible images while retaining reference SVGs. config supplies tokens
 * and assets.<key>.path/tint. Return a {path, width, height} map. original is the input,
 * input may be an explicitly tinted SVG, and target is a high-resolution derived PNG.
 * Official logos are not recolored.
 *
 * @param {object} config
 * @returns {Promise<object>}
 */
export async function prepareAssets(config) {
  const sharp = dependency('sharp');
  const directory = path.join(root, 'output/assets');
  fs.mkdirSync(directory, { recursive: true });
  const paths = fs.readdirSync(path.join(root, 'assets'))
    .filter(f => /\.(svg|png|jpe?g)$/i.test(f));
  const assets = {};
  for (const name of paths) {
    const override = config.assets[`assets/${name}`] || {};
    const original = path.resolve(root, override.path || path.join('assets', name));
    const target = path.join(directory, name.replace(/\.[^.]+$/, '.png'));
    let input = original;
    const tint = override.tint || (name.startsWith('source-50-') ? config.theme.colors.primary :
      name.startsWith('source-64-') ? config.theme.colors.border : null);
    if (/\.svg$/i.test(original) && tint)
      input = Buffer.from(fs.readFileSync(original, 'utf8').replace(/#[A-Fa-f0-9]{6}/g, `#${tint}`));
    let metadata = await sharp(input).metadata();
    if (/\.svg$/i.test(name)) {
      // Retain original SVGs in assets/. Render a high-resolution compatible bitmap for PPT viewers.
      const ratio = metadata.width / metadata.height;
      await sharp(input, { density: 192 }).resize({ width: Math.round(600 * Math.min(2, ratio)),
        height: Math.round(600 / Math.max(1, ratio)), fit: 'inside' }).png().toFile(target);
    } else await sharp(input).png().toFile(target);
    metadata = await sharp(target).metadata();
    assets[`assets/${name}`] = { path: target, width: metadata.width, height: metadata.height };
  }
  return assets;
}

/**
 * Compose seven slides using responsive grids, tokens and components. patch merges with
 * theme.mjs defaults; options defines output and whether hidden slide 68 is exposed. Return
 * pptx, manifest, config and outputPath. config validates the canvas; data supplies
 * per-slide overrides; manifest records effective geometry/fonts. This mode creates a new
 * PPTX without preserving source XML.
 *
 * @param {object} patch
 * @param {object} options
 * @returns {Promise<object>}
 */
export async function build(patch = {}, { output = 'output/responsive-slides.pptx',
  showHidden = false } = {}) {
  const config = configure(patch);
  const PptxGenJS = dependency('pptxgenjs');
  const pptx = new PptxGenJS();
  pptx.defineLayout({ name: 'BRAND_WIDE', width: config.slide.width, height: config.slide.height });
  pptx.layout = 'BRAND_WIDE';
  pptx.author = 'Context Slide Components';
  pptx.subject = 'Editable responsive reconstruction of source slides 5, 10, 21, 38, 50, 64, 68';
  pptx.title = 'Context Enriched Slide Repository — Component Library';
  pptx.company = 'Scotiabank';
  pptx.lang = 'en-CA';
  pptx.theme = { headFontFace: config.theme.fonts.heading, bodyFontFace: config.theme.fonts.body,
    lang: 'en-CA' };
  const assets = await prepareAssets(config);
  registerMasters(pptx, config, assets);
  const manifest = [];
  for (const number of [5, 10, 21, 38, 50, 64, 68]) {
    const local = config.slides[number] || {};
    const data = merge(contents[number], local.data || {});
    const slide = pptx.addSlide(data.template);
    slide.hidden = showHidden ? false : Boolean(data.hidden);
    const c = new Canvas(pptx, slide, config, number, assets, manifest);
    renderTemplate(c, data);
    slide.addNotes(`${source[number].notes}\n\nSource slide: ${number}. Source hidden: ${source[number].hidden}.
Reconstructed as a responsive PptxGenJS template. Grid: ${config.grid.columns} columns × ${config.grid.rows} rows.`);
    c.finish();
    manifest.at(-1).hidden = slide.hidden;
    manifest.at(-1).template = data.template;
  }
  const outputPath = path.resolve(root, output);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  await pptx.writeFile({ fileName: outputPath });
  const report = { slideSize: config.slide, grid: config.grid,
    fontMetrics: 'Arial advance widths; conservative estimate. Scotia rendering requires installed brand fonts.',
    theme: config.theme, slides: manifest };
  const base = outputPath.replace(/\.pptx$/i, '');
  fs.writeFileSync(`${base}.layout.json`, JSON.stringify(report, null, 2));
  console.log(`Generated ${outputPath} (${manifest.length} slides, ${config.grid.columns} × ${config.grid.rows} grid)`);
  return { pptx, manifest, config, outputPath };
}

