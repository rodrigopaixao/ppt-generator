/**
 * Public entry point: native fidelity for 71 slides or responsive composition. PptxGenJS
 * creates the scaffold, layouts and additions. The DrawingML adapter preserves objects the
 * library cannot import losslessly. Slides remain native objects rather than screenshots.
 *
 * @module generate
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { dependency } from './dependencies.mjs';
import { Grid } from './layout.mjs';
import { root } from './components.mjs';

/**
 * Run the Python adapter without a shell so paths are not interpreted as code. args excludes
 * the native_deck.py script name. Return an operation summary; large structures are written
 * as JSON. Include stderr when the process fails.
 *
 * @param {string[]} args
 * @returns {string}
 * @throws {Error}
 */
export function nativeCommand(args) {
  const result = spawnSync(process.env.PYTHON || 'python3',
    [path.join(root, 'scripts/native_deck.py'), ...args], {
      cwd: root, encoding: 'utf8', maxBuffer: 16 * 1024 * 1024,
    });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(result.stderr || result.stdout || 'DrawingML adapter failed');
  return result.stdout.trim();
}

/**
 * Validate an inch-based box within the 16:9 canvas. box is the computed region; size gives
 * physical slide dimensions. Return the same box without rounding or modification.
 *
 * @param {{x:number,y:number,w:number,h:number}} box
 * @param {{width:number,height:number}} size
 * @returns {object}
 */
export function validateAdditionBox(box, size) {
  if (!box || !['x', 'y', 'w', 'h'].every(k => Number.isFinite(box[k])) ||
    box.x < 0 || box.y < 0 || box.w <= 0 || box.h <= 0 ||
    box.x + box.w > size.width + 1e-6 || box.y + box.h > size.height + 1e-6)
    throw new Error('Addition outside the canvas: ' + JSON.stringify(box));
  return box;
}

/**
 * Create new PptxGenJS objects for import into the preserved scene. slide is the
 * destination; additions declares id/kind/text/type/box or grid/style; config supplies
 * fidelity settings and grid tracks; size is original inches. grid is zero-based and style
 * contains native options. custom. distinguishes imported additions from scaffold helper
 * objects, which are not imported.
 *
 * @param {object} slide
 * @param {object[]} additions
 * @param {object} config
 * @param {object} size
 * @returns {void}
 */
export function addNativeObjects(slide, additions, config, size) {
  const settings = { columns: 14, rows: 9, gapX: 0, gapY: 0, ...config.grid };
  const mx = settings.marginX || 0, my = settings.marginY || 0;
  const grid = new Grid({ x: mx, y: my, w: size.width-2*mx, h: size.height-2*my }, settings);
  const ids = new Set();
  for (const [index, item] of additions.entries()) {
    if (Object.keys(item).some(key => !['id', 'kind', 'text', 'type', 'box', 'grid', 'style', 'rows', 'series'].includes(key)))
      throw new Error('Addition contains unknown properties');
    const id = item.id || `addition-${index}`;
    if (ids.has(id)) throw new Error(`Duplicate addition ID: ${id}`);
    ids.add(id);
    const box = validateAdditionBox(item.grid ? grid.cell(item.grid.col, item.grid.row,
      item.grid.colSpan ?? 1, item.grid.rowSpan ?? 1) : item.box, size);
    const options = { ...box, ...item.style, objectName: `custom.${id}` };
    validateAdditionBox(options, size);
    if (item.kind === 'text') slide.addText(item.text || '', {
      fontFace: config.theme?.fonts?.body || 'Scotia', fontSize: 12,
      color: config.theme?.colors?.text || '000000', margin: 0, ...options });
    else if (item.kind === 'shape') slide.addShape(item.type || 'rect', options);
    else if (item.kind === 'table') slide.addTable(item.rows, options);
    else if (item.kind === 'chart') slide.addChart(item.type || 'bar', item.series, options);
    else throw new Error(`Unsupported addition: ${item.kind}. Use text, shape, table or chart.`);
  }
}

/**
 * Prepare PNG fallbacks only for SVG replacements requested by configuration. config is a
 * working clone and directory is private to the build. Replace SVG image fields with {path,
 * fallback}. The adapter embeds vector and raster in one native object. The unmodified
 * baseline retains its original resources.
 *
 * @param {object} config
 * @param {string} directory
 * @returns {Promise<void>}
 */
export async function preparePictureOverrides(config, directory) {
  const owners = [...Object.values(config.slides || {}), ...Object.values(config.templates || {}),
    ...Object.values(config.masters || {})];
  const patches = [...Object.values(config.elements || {}), ...owners.flatMap(owner => Object.values(owner.elements || {}))];
  let index = 0;
  for (const patch of patches) {
    if (typeof patch.image !== 'string' || !patch.image.toLowerCase().endsWith('.svg')) continue;
    const source = path.resolve(root, patch.image);
    const fallback = path.join(directory, `image-${index++}.png`);
    const sharp = dependency('sharp');
    await sharp(source, { density: 192 }).resize({ width: 1200, height: 1200, fit: 'inside' }).png().toFile(fallback);
    patch.image = { path: source, fallback };
  }
}

/**
 * Rasterizes original SVG media for readers that ignore SVG-only picture blips.
 * @param {string} sourcePath Absolute source PPTX path.
 * @param {string} directory Private build directory, removed after the build.
 * @returns {Promise<object>} Map of original OPC SVG paths to PNG fallback paths.
 * The original SVG remains in the package. Python links these fallbacks only
 * where a picture has no standard raster relationship; existing artwork is kept.
 */
export async function prepareSvgFallbacks(sourcePath, directory) {
  const Zip = dependency('jszip'), sharp = dependency('sharp');
  const archive = await Zip.loadAsync(fs.readFileSync(sourcePath));
  const result = {};
  for (const name of Object.keys(archive.files).filter(name => /^ppt\/media\/.*\.svg$/i.test(name))) {
    const target = path.join(directory, `fallback-${path.basename(name)}.png`);
    await sharp(await archive.file(name).async('nodebuffer'), { density: 192 })
      .resize({ width: 900, height: 900, fit: 'inside' }).png().toFile(target);
    result[name] = target;
  }
  return result;
}

/**
 * Generate all slides and apply only explicit overrides to the original. patch follows
 * config.fidelity.example.json; options controls the destination and whether hidden slide 68
 * is exposed. catalog describes scenes; selection controls order/subsets; scaffold is a real
 * PptxGenJS deck; configPath carries JSON to the adapter. Always remove temporary files and
 * never overwrite the reference.
 *
 * @param {object} patch
 * @param {object} options
 * @param {string} [options.output]
 * @param {boolean} [options.showHidden=false]
 * @returns {Promise<{outputPath:string,manifest:object[],report:object}>}
 */
export async function build(patch = {}, { output = 'output/recreated-slides.pptx', showHidden = false } = {}) {
  let config = structuredClone(patch);
  if (showHidden) config.showHidden = true;
  const sourcePath = path.resolve(root, config.source || '2606 Context Enriched Slide Repository.pptx');
  const catalogDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'pptxgen-catalog-'));
  let catalog;
  try {
    const catalogPath = path.join(catalogDirectory, 'catalog.json');
    nativeCommand(['catalog', '--source', sourcePath, '--catalog-output', catalogPath]);
    catalog = JSON.parse(fs.readFileSync(catalogPath));
  } finally { fs.rmSync(catalogDirectory, { recursive: true, force: true }); }
  if (config.quality) {
    const { prepareQuality } = await import('./quality.mjs');
    config = prepareQuality(config, catalog);
  }
  const selection = config.selection || catalog.slides.map(s => s.number);
  if (!selection.length || new Set(selection).size !== selection.length ||
      selection.some(n => !catalog.slides.some(s => s.number === n)))
    throw new Error('selection must contain existing slides without duplicates');
  const PptxGenJS = dependency('pptxgenjs');
  const pptx = new PptxGenJS();
  const size = catalog.slide;
  if (Math.abs(size.width/size.height-16/9) > 1e-5) throw new Error('The reference must use a 16:9 aspect ratio');
  pptx.defineLayout({ name: 'SOURCE_16_9', width: size.width, height: size.height });
  pptx.layout = 'SOURCE_16_9';
  pptx.title = 'Context Enriched Slide Repository — 71 configurable native slides';
  pptx.author = 'PptxGenJS / Context Slide Components';
  pptx.subject = 'Preserved source DrawingML with configurable native elements';
  pptx.company = 'Scotiabank';
  const layouts = new Set(selection.map(n => catalog.slides[n-1].layout));
  for (const layout of layouts) pptx.defineSlideMaster({ title: layout, objects: [], background: { color: 'FFFFFF' } });
  for (const number of selection) {
    const descriptor = catalog.slides[number-1];
    const slide = pptx.addSlide(descriptor.layout);
    slide.hidden = showHidden ? false : descriptor.hidden;
    slide.addText(descriptor.title, { x: 0.56, y: 0.5, w: size.width-1.12,
      h: 0.8, fontSize: 18, objectName: 'scaffold.title' });
    addNativeObjects(slide, config.additions?.[number] || [], config, size);
  }
  for (const number of Object.keys(config.additions || {}))
    if (!selection.includes(Number(number))) throw new Error(`Additions target a slide outside the selection: ${number}`);
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'pptxgen-fidelity-'));
  const outputPath = path.resolve(root, output);
  if (!outputPath.toLowerCase().endsWith('.pptx')) throw new Error('output must end in .pptx');
  try {
    const scaffold = path.join(directory, 'scaffold.pptx');
    const configPath = path.join(directory, 'config.json');
    await preparePictureOverrides(config, directory);
    if (config.quality) config.quality._svgFallbacks = await prepareSvgFallbacks(sourcePath, directory);
    fs.writeFileSync(configPath, JSON.stringify(config));
    await pptx.writeFile({ fileName: scaffold });
    const summary = nativeCommand(['build', '--source', sourcePath, '--scaffold', scaffold,
      '--config', configPath, '--output', outputPath]);
    const report = JSON.parse(fs.readFileSync(outputPath.replace(/\.pptx$/i, '.layout.json')));
    console.log(`Generated ${outputPath}: ${summary}`);
    return { outputPath, manifest: report.slides, report };
  } finally { fs.rmSync(directory, { recursive: true, force: true }); }
}

/**
 * Parse recognized CLI arguments without a shell or changes to the source JSON. args follows
 * the script name. Return mode, patch and build options.
 *
 * @param {string[]} args
 * @returns {{mode:string,patch:object,options:object}}
 */
export function parseArguments(args) {
  const known = new Set(['--mode', '--config', '--output', '--font', '--grid', '--slides', '--show-hidden', '--debug']);
  const flags = new Set(['--show-hidden', '--debug']);
  const values = {};
  for (let i = 0; i < args.length; i++) {
    const key = args[i];
    if (!known.has(key)) throw new Error(`Unknown argument: ${key}`);
    if (flags.has(key)) values[key] = true;
    else {
      if (!args[i+1] || args[i+1].startsWith('--')) throw new Error(`Missing value for ${key}`);
      values[key] = args[++i];
    }
  }
  const patch = values['--config'] ? JSON.parse(fs.readFileSync(values['--config'], 'utf8')) : {};
  const mode = values['--mode'] || patch.mode || 'fidelity';
  if (!['fidelity', 'responsive'].includes(mode)) throw new Error('mode must be fidelity or responsive');
  if (values['--font']) patch.theme = { ...patch.theme, fonts: { ...patch.theme?.fonts,
    body: values['--font'], heading: values['--font'] } };
  if (values['--grid']) {
    const [columns, rows] = values['--grid'].split(/x|:/).map(Number);
    patch.grid = { ...patch.grid, columns, rows };
  }
  if (values['--slides']) patch.selection = values['--slides'].split(',').map(Number);
  if (values['--debug']) {
    if (mode !== 'responsive') throw new Error('--debug is available with --mode responsive');
    patch.template = { ...patch.template, showGrid: true };
  }
  delete patch.mode;
  return { mode, patch, options: { output: values['--output'] ||
    (mode === 'responsive' ? 'output/responsive-slides.pptx' : 'output/recreated-slides.pptx'),
    showHidden: Boolean(values['--show-hidden']) } };
}

if (import.meta.url === pathToFileURL(process.argv[1] || '').href) {
  const { mode, patch, options } = parseArguments(process.argv.slice(2));
  if (mode === 'responsive') {
    const { build: buildResponsive } = await import('./responsive.mjs');
    await buildResponsive(patch, options);
  } else await build(patch, options);
}
