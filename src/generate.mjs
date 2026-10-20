/**
 * Entrada pública: fidelidade nativa para 71 slides ou composição adaptativa.
 * PptxGenJS cria scaffold/layouts/adições. O adaptador DrawingML preserva tudo
 * que a biblioteca não consegue importar sem perdas. Nenhum slide é uma imagem.
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
 * Executa o adaptador Python sem shell; caminhos não são interpretados como código.
 * @param {string[]} args Argumentos de native_deck.py, sem o nome do script.
 * @returns {string} Resumo da operação; estruturas grandes são gravadas em JSON.
 * @throws {Error} Se o processo falhar, inclui stderr para diagnóstico.
 */
export function nativeCommand(args) {
  const result = spawnSync(process.env.PYTHON || 'python3',
    [path.join(root, 'scripts/native_deck.py'), ...args], {
      cwd: root, encoding: 'utf8', maxBuffer: 16 * 1024 * 1024,
    });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(result.stderr || result.stdout || 'Falha no adaptador DrawingML');
  return result.stdout.trim();
}

/**
 * Valida uma caixa em polegadas dentro do canvas 16:9.
 * @param {{x:number,y:number,w:number,h:number}} box Região calculada.
 * @param {{width:number,height:number}} size Dimensões físicas do slide.
 * @returns {object} A mesma caixa, sem arredondamento ou alterações.
 */
export function validateAdditionBox(box, size) {
  if (!box || !['x', 'y', 'w', 'h'].every(k => Number.isFinite(box[k])) ||
    box.x < 0 || box.y < 0 || box.w <= 0 || box.h <= 0 ||
    box.x + box.w > size.width + 1e-6 || box.y + box.h > size.height + 1e-6)
    throw new Error('Adição fora do canvas: ' + JSON.stringify(box));
  return box;
}

/**
 * Cria objetos novos com PptxGenJS para importar na cena preservada.
 * @param {object} slide Slide PptxGenJS a modificar.
 * @param {object[]} additions Declarações {id,kind,text,type,box|grid,style}.
 * @param {object} config Configuração fiel e tracks do grid.
 * @param {object} size Dimensões originais, em polegadas.
 * @returns {void}
 * grid usa base zero; style são opções nativas da biblioteca. O prefixo custom.
 * distingue adições dos objetos auxiliares do scaffold, que não são importados.
 */
export function addNativeObjects(slide, additions, config, size) {
  const settings = { columns: 14, rows: 9, gapX: 0, gapY: 0, ...config.grid };
  const mx = settings.marginX || 0, my = settings.marginY || 0;
  const grid = new Grid({ x: mx, y: my, w: size.width-2*mx, h: size.height-2*my }, settings);
  const ids = new Set();
  for (const [index, item] of additions.entries()) {
    if (Object.keys(item).some(key => !['id', 'kind', 'text', 'type', 'box', 'grid', 'style', 'rows', 'series'].includes(key)))
      throw new Error('Adição contém propriedades desconhecidas');
    const id = item.id || `addition-${index}`;
    if (ids.has(id)) throw new Error(`ID de adição duplicado: ${id}`);
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
    else throw new Error(`Adição não suportada: ${item.kind}. Use text, shape, table ou chart.`);
  }
}

/**
 * Prepara fallback PNG apenas para substituições SVG solicitadas na configuração.
 * @param {object} config Configuração de trabalho, já clonada da entrada.
 * @param {string} directory Diretório temporário privado do build.
 * @returns {Promise<void>} Troca somente os campos image SVG por {path,fallback}.
 * O adaptador incorpora vetor e raster no mesmo objeto nativo. O baseline não
 * passa por esta conversão e mantém todos os recursos originais intactos.
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
 * Gera todos os slides e aplica somente overrides explícitos sobre o original.
 * @param {object} patch Contrato de config.fidelity.example.json.
 * @param {object} options Opções de execução.
 * @param {string} [options.output] Arquivo de destino relativo ou absoluto.
 * @param {boolean} [options.showHidden=false] Expõe o slide 68 para revisão.
 * @returns {Promise<{outputPath:string,manifest:object[],report:object}>}
 * catalog descreve as cenas; selection define ordem/recorte; scaffold é um PPTX
 * real do PptxGenJS; configPath transporta o JSON ao adaptador. O diretório
 * temporário sempre é removido. A referência nunca é sobrescrita.
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
    throw new Error('selection precisa conter slides existentes, sem repetições');
  const PptxGenJS = dependency('pptxgenjs');
  const pptx = new PptxGenJS();
  const size = catalog.slide;
  if (Math.abs(size.width/size.height-16/9) > 1e-5) throw new Error('A referência precisa ser 16:9');
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
    if (!selection.includes(Number(number))) throw new Error(`Adições em slide fora da seleção: ${number}`);
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'pptxgen-fidelity-'));
  const outputPath = path.resolve(root, output);
  if (!outputPath.toLowerCase().endsWith('.pptx')) throw new Error('output deve terminar em .pptx');
  try {
    const scaffold = path.join(directory, 'scaffold.pptx');
    const configPath = path.join(directory, 'config.json');
    await preparePictureOverrides(config, directory);
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
 * Interpreta argumentos conhecidos sem shell e sem modificar o JSON de origem.
 * @param {string[]} args Argumentos depois do nome do script.
 * @returns {{mode:string,patch:object,options:object}} Parâmetros para o build.
 */
export function parseArguments(args) {
  const known = new Set(['--mode', '--config', '--output', '--font', '--grid', '--slides', '--show-hidden', '--debug']);
  const flags = new Set(['--show-hidden', '--debug']);
  const values = {};
  for (let i = 0; i < args.length; i++) {
    const key = args[i];
    if (!known.has(key)) throw new Error(`Argumento desconhecido: ${key}`);
    if (flags.has(key)) values[key] = true;
    else {
      if (!args[i+1] || args[i+1].startsWith('--')) throw new Error(`Falta valor para ${key}`);
      values[key] = args[++i];
    }
  }
  const patch = values['--config'] ? JSON.parse(fs.readFileSync(values['--config'], 'utf8')) : {};
  const mode = values['--mode'] || patch.mode || 'fidelity';
  if (!['fidelity', 'responsive'].includes(mode)) throw new Error('mode deve ser fidelity ou responsive');
  if (values['--font']) patch.theme = { ...patch.theme, fonts: { ...patch.theme?.fonts,
    body: values['--font'], heading: values['--font'] } };
  if (values['--grid']) {
    const [columns, rows] = values['--grid'].split(/x|:/).map(Number);
    patch.grid = { ...patch.grid, columns, rows };
  }
  if (values['--slides']) patch.selection = values['--slides'].split(',').map(Number);
  if (values['--debug']) {
    if (mode !== 'responsive') throw new Error('--debug está disponível em --mode responsive');
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
