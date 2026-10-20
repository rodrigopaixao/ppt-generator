/**
 * Componentes editáveis do modo responsive. Coordenadas são polegadas; fontes
 * são pontos; IDs são estáveis por slide e aparecem no manifesto de layout.
 * Não substituem o adaptador fiel: este mantém todos os objetos originais.
 * @module components
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { merge } from './theme.mjs';
import { inset, relative, split, wrap } from './layout.mjs';

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const metrics = JSON.parse(fs.readFileSync(path.join(root, 'data/font-metrics.json')));
/** Normaliza string/rich runs para medição; conserva o texto, sem aplicar estilos. */
const plain = value => Array.isArray(value) ? value.map(r => r.text || '').join('') : String(value ?? '');

/**
 * Estima linhas usando avanços reais de caracteres Arial extraídos em em.
 * @param {string|object[]} value Texto simples ou runs PptxGenJS.
 * @param {number} width Largura útil em polegadas.
 * @param {number} size Fonte em pontos.
 * @param {boolean} bold Seleciona tabela de larguras em negrito.
 * @param {number} safety Margem multiplicativa para variação entre renderizadores.
 * @returns {number} Total de linhas; palavras maiores que a caixa são quebradas.
 * used acumula largura da linha; measure converte avanço em em para polegadas.
 */
export function textLines(value, width, size, bold = false, safety = 1.05) {
  const widths = metrics.widths[bold ? 'bold' : 'regular'];
  /** Soma avanços de uma palavra e converte em -> pt -> in, com margem de segurança. */
  const measure = word => [...word].reduce((sum, c) => sum + (widths[c] ?? 0.56), 0) * size / 72 * safety;
  return plain(value).split('\n').reduce((total, paragraph) => {
    let lines = 1, used = 0;
    for (const word of paragraph.split(/(\s+)/).filter(Boolean)) {
      const w = measure(word);
      if (used && used + w > width) { lines++; used = 0; }
      if (w > width) { lines += Math.floor(w / width); used = w % width; }
      else used += w;
    }
    return total + lines;
  }, 0);
}

/**
 * Converte linhas estimadas em altura física, incluindo espaço entre parágrafos.
 * @param {string|object[]} value Conteúdo a medir.
 * @param {number} width Largura em polegadas.
 * @param {number} size Fonte em pt.
 * @param {object} options bold, safety, leading e paraSpaceAfter (pt).
 * @returns {number} Altura em polegadas; largura inválida retorna Infinity.
 */
export function textHeight(value, width, size, options = {}) {
  if (width <= 0) return Infinity;
  const lines = textLines(value, width, size, options.bold, options.safety ?? 1.05);
  return lines * size / 72 * (options.leading ?? 1.16) +
    (plain(value).split('\n').length - 1) * (options.paraSpaceAfter ?? 0) / 72;
}

/**
 * Procura uma fonte que acomode TODO o texto, reduzindo em passos de 0,25 pt.
 * @param {string|object[]} value Conteúdo completo.
 * @param {object} box Caixa útil, já sem padding.
 * @param {object} options fontSize é o máximo; minFontSize é o limite inferior.
 * @returns {number} Fonte escolhida. Rejeita conteúdo que não caiba no mínimo,
 * sem truncar texto nem adicionar slides silenciosamente.
 */
export function fitText(value, box, options = {}) {
  const max = options.fontSize ?? 10.5, min = options.minFontSize ?? 7;
  let size = max;
  while (size > min && textHeight(value, box.w, size, options) > box.h)
    size = Math.max(min, Math.round((size - 0.25) * 100) / 100);
  if (textHeight(value, box.w, size, options) > box.h + 0.01)
    throw new Error(`Text cannot fit at minimum ${min}pt: ${plain(value).slice(0, 85)}`);
  return size;
}

export class Canvas {
  /**
   * Encapsula um slide e sua auditoria sem manter estado global de desenho.
   * @param {object} pptx Instância PptxGenJS.
   * @param {object} slide Slide nativo a preencher.
   * @param {object} config Configuração adaptativa resolvida.
   * @param {number} number Número de origem, usado no namespace dos IDs.
   * @param {object} assets Mapa de caminhos e dimensões dos assets preparados.
   * @param {object[]} manifest Destino compartilhado de registros dos slides.
   * records acumula objetos do slide; theme aponta para os tokens resolvidos.
   */
  constructor(pptx, slide, config, number, assets, manifest) {
    Object.assign(this, { pptx, slide, config, number, assets, manifest });
    this.theme = config.theme;
    this.records = [];
  }
  /**
   * Resolve opções na ordem: defaults locais, componente global, slide, elemento.
   * @param {string} kind Família (text, table, collection etc.).
   * @param {string} id Identificador local, sem o prefixo do slide.
   * @param {object} local Padrões específicos dessa chamada.
   * @returns {object} Cópia mesclada; o elemento é sempre a maior precedência.
   */
  options(kind, id, local = {}) {
    return merge(merge(merge(local, this.config.components[kind] || {}),
      this.config.slides[this.number]?.components?.[kind] || {}),
      this.config.elements[`${this.number}.${id}`] || {});
  }
  /**
   * Valida limites do canvas e registra um objeto para QA e configuração futura.
   * @param {string} id ID local.
   * @param {object} box Caixa global em polegadas.
   * @param {object} extra Metadados como kind, text, fontSize e series.
   * @returns {object} Registro inserido. Não desenha nada.
   */
  record(id, box, extra = {}) {
    const { width, height } = this.config.slide;
    if (![box.x, box.y, box.w, box.h].every(Number.isFinite) || box.w < 0 || box.h < 0 ||
        box.x < -0.001 || box.y < -0.001 || box.x + box.w > width + 0.001 || box.y + box.h > height + 0.001)
      throw new Error(`Slide ${this.number}: ${id} exceeds slide bounds: ${JSON.stringify(box)}`);
    const entry = { id, box: { ...box }, ...extra };
    this.records.push(entry);
    return entry;
  }
  /**
   * Cria texto/rich text nativo com padding, override e ajuste de fonte.
   * @param {string} id ID configurável do texto.
   * @param {string|object[]} value Texto ou runs.
   * @param {object} box Região externa em polegadas.
   * @param {object} style Defaults e opções PptxGenJS.
   * @returns {void} Modifica slide e records; visible=false não cria objeto.
   * b é a caixa com override; inner desconta padding; fontSize vem de fitText.
   */
  text(id, value, box, style = {}) {
    const o = this.options('text', id, style);
    if (o.visible === false) return;
    value = o.text ?? value;
    const b = { ...box, ...o.box };
    const pad = o.padding ?? 0;
    const inner = pad ? inset(b, pad) : b;
    const fontSize = fitText(value, inner, { fontSize: this.theme.type.body,
      minFontSize: 6.5, ...o });
    const { box: _, padding: __, minFontSize: ___, visible: ____, safety: _____,
      leading: ______, text: _______, ...pptOptions } = o;
    this.slide.addText(value, {
      ...inner, fontFace: this.theme.fonts.body, color: this.theme.colors.text,
      margin: 0, breakLine: false, valign: 'top', fontSize,
      lineSpacingMultiple: o.leading ?? 1.10, paraSpaceAfterPt: o.paraSpaceAfter ?? 0,
      ...pptOptions, fontSize, objectName: `${this.number}.${id}`,
    });
    this.record(id, inner, { kind: 'text', text: plain(value), fontSize,
      estimatedHeight: textHeight(value, inner.w, fontSize, o) });
  }
  /**
   * Cria forma/conector nativo e registra seus limites.
   * @param {string} id ID estável.
   * @param {object} box Caixa em polegadas; linhas podem ter dimensão zero.
   * @param {object} style type, fill, line e demais opções PptxGenJS.
   * @returns {void} A geometria permanece editável no PowerPoint.
   */
  shape(id, box, style = {}) {
    const o = this.options('shape', id, style);
    if (o.visible === false) return;
    const b = { ...box, ...o.box };
    const { type = 'rect', box: _, visible: __, ...opts } = o;
    this.slide.addShape(type, { ...b, line: { color: this.theme.colors.border, width: this.theme.line.thin },
      fill: { color: this.theme.colors.paper, transparency: 100 }, ...opts,
      objectName: `${this.number}.${id}` });
    this.record(id, b, { kind: 'shape' });
  }
  /**
   * Converte dois extremos em uma forma line, inclusive em direção invertida.
   * @param {string} id ID do conector.
   * @param {number} x1 Primeiro x, em polegadas.
   * @param {number} y1 Primeiro y.
   * @param {number} x2 Segundo x.
   * @param {number} y2 Segundo y.
   * @param {object} options Propriedades de linha, cor, espessura e setas.
   * @returns {void} flipV conserva o sentido da diagonal após normalizar a caixa.
   */
  line(id, x1, y1, x2, y2, options = {}) {
    this.shape(id, { x: Math.min(x1, x2), y: Math.min(y1, y2),
      w: Math.abs(x2 - x1), h: Math.abs(y2 - y1) }, {
      type: 'line', flipV: (x2 - x1) * (y2 - y1) < 0,
      line: { color: this.theme.colors.border, width: this.theme.line.thin, ...options },
    });
  }
  /**
   * Insere asset original com proporção preservada e centralização contain.
   * @param {string} id ID do elemento.
   * @param {string} asset Chave no mapa assets (não é URL arbitrária).
   * @param {object} box Região disponível em polegadas.
   * @param {object} options Overrides de asset, box e opções PptxGenJS.
   * @returns {void} scale é o menor fator entre largura e altura; evita distorção.
   */
  image(id, asset, box, options = {}) {
    const o = this.options('image', id, options);
    asset = o.asset ?? asset;
    if (o.visible === false || !asset) return;
    const b = { ...box, ...o.box };
    const { box: _, visible: __, asset: ___, ...rest } = o;
    const image = this.assets[asset];
    if (!image) throw new Error(`Asset not prepared: ${asset}`);
    const scale = Math.min(b.w / image.width, b.h / image.height);
    const w = image.width * scale, h = image.height * scale;
    this.slide.addImage({ path: image.path,
      x: b.x + (b.w - w) / 2, y: b.y + (b.h - h) / 2, w, h,
      ...rest, objectName: `${this.number}.${id}` });
    this.record(id, b, { kind: 'image', asset });
  }
  /**
   * Finaliza a auditoria e, se solicitado, desenha limites de debug dos textos.
   * @returns {void} Acrescenta exatamente um registro de slide ao manifest.
   * Debug não faz parte de um build fiel e fica limitado ao modo responsive.
   */
  finish() {
    if (this.config.template.showGrid) {
      for (const r of this.records.filter(r => r.kind === 'text'))
        this.slide.addShape('rect', { ...r.box, line: { color: '00AACC', width: 0.3, transparency: 50 },
          fill: { color: 'FFFFFF', transparency: 100 } });
    }
    this.manifest.push({ sourceNumber: this.number, elements: this.records });
  }
}

/**
 * Converte parágrafos extraídos para runs PptxGenJS, mantendo ênfase e sobrescrito.
 * @param {object[]} paragraphs Lista com text, runs, level e bullet.
 * @param {object} options headingColor remapeia vermelhos de marca; bullet ativa
 * os marcadores visíveis. Os estilos dos runs não alteram o conteúdo textual.
 * @returns {object[]} Runs com quebras entre parágrafos, prontos para addText.
 */
export function richParagraphs(paragraphs, { headingColor, bullet = true } = {}) {
  return paragraphs.flatMap((p, index) => {
    const prefix = bullet && p.bullet ? `${'  '.repeat(p.level)}• ` : '';
    const runs = p.runs.map(r => ({ text: r.text,
      options: { bold: r.style.b === '1', italic: r.style.i === '1',
        ...(r.style.color ? { color: /^(EC111A|E1111A|FF0000)$/i.test(r.style.color)
          ? headingColor || r.style.color : r.style.color } : {}),
        ...(r.style.baseline > 0 ? { superscript: true } : {}),
      } }));
    if (prefix) runs.unshift({ text: prefix, options: {} });
    if (index < paragraphs.length - 1) runs.push({ text: '\n', options: {} });
    return runs;
  });
}

/**
 * Escreve tabela nativa depois de medir cada célula.
 * @param {Canvas} c Contexto de desenho.
 * @param {string} id ID configurável.
 * @param {string[][]} values Matriz de células.
 * @param {object} box Região da tabela em polegadas.
 * @param {object} options weights define larguras proporcionais; padding é in;
 * rowStyles/cellStyles personalizam linhas/células; pptx expõe opções nativas.
 * @returns {{widths:number[],heights:number[]}} Dimensões efetivas das colunas/linhas.
 * measured soma a altura mínima; o excedente da caixa se distribui entre linhas.
 * Paginação automática fica desligada para não alterar a contagem de slides.
 */
export function table(c, id, values, box, options = {}) {
  const o = c.options('table', id, {
    weights: Array(values[0].length).fill(1), fontSize: 10,
    minFontSize: 7, padding: 0.045, headerFill: c.theme.colors.primary,
    headerColor: c.theme.colors.paper, header: true, ...options,
  });
  values = o.values ?? values;
  if (o.visible === false) return { widths: [], heights: [] };
  const b = { ...box, ...o.box };
  const sum = o.weights.reduce((a, b) => a + b, 0);
  const widths = o.weights.map(w => b.w * w / sum);
  let size = o.fontSize, heights;
  /** Combina estilo de linha e célula, com a célula tendo maior precedência. */
  const rowStyle = (r, col) => merge(o.rowStyles?.[r] || {}, o.cellStyles?.[`${r}.${col}`] || {});
  /** Calcula altura mínima de cada linha a partir de sua célula mais alta. */
  const measure = () => values.map((row, r) => Math.max(...row.map((value, col) =>
    textHeight(value, widths[col] - o.padding * 2, size, {
      bold: (o.header && r === 0) || rowStyle(r, col).bold,
      leading: 1.12, safety: 1.07,
    }) + o.padding * 2)));
  heights = measure();
  while (heights.reduce((a, b) => a + b, 0) > b.h && size > o.minFontSize) {
    size = Math.max(o.minFontSize, size - 0.25); heights = measure();
  }
  const measured = heights.reduce((a, b) => a + b, 0);
  if (measured > b.h + 0.01) throw new Error(`Table ${id} does not fit at ${size}pt`);
  // Distribute spare space over rows. Native table rowH is a minimum; measurement includes safety.
  heights = heights.map(h => h + (b.h - measured) / heights.length);
  const rows = values.map((row, r) => row.map((value, col) => ({ text: value, options: {
    bold: o.header && r === 0, color: o.header && r === 0 ? o.headerColor : c.theme.colors.text,
    fill: o.header && r === 0 ? o.headerFill : c.theme.colors.paper,
    align: col === 0 || o.align === 'left' ? 'left' : 'center',
    valign: 'mid', ...rowStyle(r, col),
  } })));
  c.slide.addTable(rows, {
    ...b, colW: widths, rowH: heights, fontFace: c.theme.fonts.body, fontSize: size,
    color: c.theme.colors.text, margin: o.padding * 72, border: {
      type: 'solid', pt: c.theme.line.thin, color: c.theme.colors.border },
    autoPage: false, verbose: false, paraSpaceAfterPt: 0,
    ...o.pptx, objectName: `${c.number}.${id}`,
  });
  c.record(id, b, { kind: 'table', rows: values.length, columns: widths.length,
    fontSize: size, rowHeights: heights, estimatedHeight: measured,
    text: values.map(r => r.join('\t')).join('\n') });
  return { widths, heights };
}

/**
 * Faz reflow e invoca o renderer de cada item na ordem de leitura.
 * @param {Canvas} c Contexto de desenho.
 * @param {string} id ID do conjunto; filhos recebem .0, .1 etc.
 * @param {object[]} items Conteúdo da coleção.
 * @param {object} box Espaço total.
 * @param {object} options minWidth/gap são in; minColumnSpan vincula ao grid.
 * @param {Function} render Callback (item, box, id, options) que compõe cada filho.
 * @returns {void} A entrada não é reordenada nem modificada.
 */
export function collection(c, id, items, box, options, render) {
  const o = c.options('collection', id, { minWidth: 1.8, gap: c.theme.spacing.gap,
    maxColumns: items.length, ...options });
  if (o.minColumnSpan) o.maxColumns = Math.min(o.maxColumns,
    Math.max(1, Math.floor(c.config.grid.columns / o.minColumnSpan)));
  const boxes = wrap({ ...box, ...o.box }, items.length, o);
  items.forEach((item, i) => render(item, boxes[i], `${id}.${i}`, o));
}

/**
 * Compõe moldura e faixa de título e devolve a área útil do painel.
 * @param {Canvas} c Contexto.
 * @param {string} id Prefixo dos elementos frame/bar/title.
 * @param {object} box Caixa externa.
 * @param {string} title Texto da faixa.
 * @param {object} options headingRatio é fração da altura; padding é in;
 * frame/bar/title aceitam estilos separados.
 * @returns {object} Caixa interna disponível para conteúdo do chamador.
 */
export function panel(c, id, box, title, options = {}) {
  const o = c.options('panel', id, { padding: c.theme.spacing.padding,
    headingRatio: 0.065, headingFontSize: 11, ...options });
  const b = { ...box, ...o.box };
  c.shape(`${id}.frame`, b, { line: { color: c.theme.colors.primary, width: 0.8 },
    fill: { color: c.theme.colors.paper }, ...o.frame });
  const header = relative(b, 0, 0, 1, o.headingRatio);
  c.shape(`${id}.bar`, header, { fill: { color: c.theme.colors.primary },
    line: { color: c.theme.colors.primary }, ...o.bar });
  c.text(`${id}.title`, title, inset(header, { left: 0.05, right: 0.05, top: 0.025, bottom: 0.025 }), {
    color: c.theme.colors.paper, fontSize: o.headingFontSize, bold: true,
    align: 'center', valign: 'mid', ...o.title });
  return inset(relative(b, 0, o.headingRatio, 1, 1 - o.headingRatio), o.padding);
}

/**
 * Cria rosca nativa com um ponto branco extra para produzir o semicírculo.
 * @param {Canvas} c Contexto.
 * @param {string} id ID do gráfico.
 * @param {object} series {labels,values}; o último valor é espaçador, não indicador.
 * @param {object} box Área física do gráfico.
 * @param {object} options holeSize, firstSliceAng, series e pptx são configuráveis.
 * @returns {object} Série efetiva após overrides, para manter rótulos sincronizados.
 */
export function donut(c, id, series, box, options = {}) {
  const o = c.options('chart', id, { holeSize: 53, firstSliceAng: 270,
    fontSize: 8.5, ...options });
  const b = { ...box, ...o.box };
  series = o.series ?? series;
  if (o.visible === false) return series;
  const colors = [c.theme.colors.complete, c.theme.colors.inProgress,
    c.theme.colors.notStarted, c.theme.colors.paper];
  c.slide.addChart(c.pptx.ChartType.doughnut, [{ name: 'Work packages', labels: series.labels,
    values: series.values }], { ...b, holeSize: o.holeSize, firstSliceAng: o.firstSliceAng,
    chartColors: colors, showLegend: false, showTitle: false, showValue: false,
    showBorder: false, showCatName: false, showPercent: false,
    showSerName: false, showMarker: false,
    showLine: false, layout: { x: 0.02, y: 0.02, w: 0.96, h: 0.96 },
    border: { pt: 0, color: c.theme.colors.paper },
    ...o.pptx, objectName: `${c.number}.${id}` });
  c.record(id, b, { kind: 'chart', series });
  return series;
}

/**
 * Divide uma região entre título e texto, sem acrescentar um fundo decorativo.
 * @param {Canvas} c Contexto.
 * @param {string} id Prefixo de heading/body.
 * @param {string} title Rótulo.
 * @param {string|object[]} body Texto ou runs.
 * @param {object} box Região total.
 * @param {object} options titleRatio define a divisão; heading/body são overrides.
 * @returns {void} Ambos os textos são medidos e ajustados independentemente.
 */
export function labelBody(c, id, title, body, box, options = {}) {
  const o = c.options('labelBody', id, { titleRatio: 0.18, titleFontSize: 10,
    fontSize: 10, ...options });
  const areas = split({ ...box, ...o.box }, [o.titleRatio, 1 - o.titleRatio], 'y', 0.04);
  c.text(`${id}.heading`, title, areas[0], { fontSize: o.titleFontSize,
    bold: true, color: o.color ?? c.theme.colors.text, ...o.heading });
  c.text(`${id}.body`, body, areas[1], { fontSize: o.fontSize, ...o.body });
}
