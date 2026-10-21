/**
 * Editable components for responsive mode. Coordinates use inches; font sizes use points.
 * IDs are stable within each slide and appear in the layout manifest. The fidelity adapter
 * separately preserves original objects.
 *
 * @module components
 */
import fs from 'node:fs';
import { editRichText } from './text-edit.mjs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { merge } from './theme.mjs';
import { inset, relative, split, wrap } from './layout.mjs';

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const metrics = JSON.parse(fs.readFileSync(path.join(root, 'data/font-metrics.json')));
/**
 * Normalize plain text/rich-text runs for measurement without changing wording or applying
 * styles.
 */
const plain = value => Array.isArray(value) ? value.map(r => r.text || '').join('') : String(value ?? '');

/**
 * Estimate line counts using measured Arial character advances in em. value is plain text or
 * PptxGenJS runs; width is usable inches and size is points. bold selects bold metrics;
 * safety allows for renderer differences. Split words wider than the box. used accumulates
 * line width; measure converts em advances to inches.
 *
 * @param {string|object[]} value
 * @param {number} width
 * @param {number} size
 * @param {boolean} bold
 * @param {number} safety
 * @returns {number}
 */
export function textLines(value, width, size, bold = false, safety = 1.05) {
  const widths = metrics.widths[bold ? 'bold' : 'regular'];
  /**
   * Sum word advances and convert em to points to inches with a safety factor.
   */
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
 * Convert estimated lines to physical height, including paragraph spacing. width is inches
 * and size is points. options accepts bold, safety, leading and paraSpaceAfter in points.
 * Return height in inches or Infinity for an invalid width.
 *
 * @param {string|object[]} value
 * @param {number} width
 * @param {number} size
 * @param {object} options
 * @returns {number}
 */
export function textHeight(value, width, size, options = {}) {
  if (width <= 0) return Infinity;
  const lines = textLines(value, width, size, options.bold, options.safety ?? 1.05);
  return lines * size / 72 * (options.leading ?? 1.16) +
    (plain(value).split('\n').length - 1) * (options.paraSpaceAfter ?? 0) / 72;
}

/**
 * Find a font size that fits all text, shrinking in 0.25-point steps. box is usable space
 * after padding. fontSize is the maximum and minFontSize the lower limit. Reject content
 * that cannot fit at the minimum rather than truncating text or silently adding slides.
 *
 * @param {string|object[]} value
 * @param {object} box
 * @param {object} options
 * @returns {number}
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
   * Encapsulate a slide and its audit without global drawing state. pptx is the PptxGenJS
   * instance; slide is the native destination; config contains resolved responsive settings.
   * number namespaces source IDs; assets maps prepared paths/dimensions. manifest collects
   * slide records. records accumulates objects and theme references resolved tokens.
   *
   * @param {object} pptx
   * @param {object} slide
   * @param {object} config
   * @param {number} number
   * @param {object} assets
   * @param {object[]} manifest
   */
  constructor(pptx, slide, config, number, assets, manifest) {
    Object.assign(this, { pptx, slide, config, number, assets, manifest });
    this.theme = config.theme;
    this.records = [];
  }
  /**
   * Resolve options in order: local defaults, global component, slide, then element. kind is
   * the component family; id omits the slide prefix. local contains call-specific defaults.
   * Return a merged copy with element options taking precedence.
   *
   * @param {string} kind
   * @param {string} id
   * @param {object} local
   * @returns {object}
   */
  options(kind, id, local = {}) {
    return merge(merge(merge(local, this.config.components[kind] || {}),
      this.config.slides[this.number]?.components?.[kind] || {}),
      this.config.elements[`${this.number}.${id}`] || {});
  }
  /**
   * Validate canvas bounds and record an object for QA and future configuration. id is local,
   * box uses global inches, and extra holds kind/text/fontSize/series metadata. Return the
   * inserted record without drawing.
   *
   * @param {string} id
   * @param {object} box
   * @param {object} extra
   * @returns {object}
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
   * Create native plain/rich text with padding, overrides and font fitting. id is
   * configurable; value is text or runs; box uses external inches; style supplies defaults and
   * PptxGenJS options. Update slide and records unless visible=false. b includes box
   * overrides; inner subtracts padding; fitText resolves fontSize.
   *
   * @param {string} id
   * @param {string|object[]} value
   * @param {object} box
   * @param {object} style
   * @returns {void}
   */
  text(id, value, box, style = {}) {
    const o = this.options('text', id, style);
    if (o.visible === false) return;
    value = o.text === undefined ? value : editRichText(value, o.text);
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
   * Create a native shape/connector and record its bounds. id is stable; box uses inches and
   * lines may have a zero dimension. style accepts type, fill, line and other PptxGenJS
   * options. Geometry stays editable in PowerPoint.
   *
   * @param {string} id
   * @param {object} box
   * @param {object} style
   * @returns {void}
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
   * Convert two endpoints to a line shape, including reversed directions. x1/y1/x2/y2 use
   * inches; options controls color, width and arrows. flipV preserves diagonal direction after
   * normalizing the box.
   *
   * @param {string} id
   * @param {number} x1
   * @param {number} y1
   * @param {number} x2
   * @param {number} y2
   * @param {object} options
   * @returns {void}
   */
  line(id, x1, y1, x2, y2, options = {}) {
    this.shape(id, { x: Math.min(x1, x2), y: Math.min(y1, y2),
      w: Math.abs(x2 - x1), h: Math.abs(y2 - y1) }, {
      type: 'line', flipV: (x2 - x1) * (y2 - y1) < 0,
      line: { color: this.theme.colors.border, width: this.theme.line.thin, ...options },
    });
  }
  /**
   * Insert original artwork with preserved aspect ratio and centered contain fitting. asset is
   * a key in the prepared assets map, not an arbitrary URL. box uses inches; options may
   * override asset, box and PptxGenJS properties. scale uses the smaller width/height factor
   * to avoid distortion.
   *
   * @param {string} id
   * @param {string} asset
   * @param {object} box
   * @param {object} options
   * @returns {void}
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
   * Finish the audit and optionally draw text debug bounds. Append exactly one slide record to
   * manifest. Debug rendering is restricted to responsive mode and is not part of a fidelity
   * build.
   *
   * @returns {void}
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
 * Convert extracted paragraphs to PptxGenJS runs, retaining emphasis and superscripts.
 * paragraphs contains text/runs/level/bullet; headingColor remaps brand reds and bullet
 * enables visible markers. Run styles do not change wording. Return runs with paragraph
 * breaks, ready for addText.
 *
 * @param {object[]} paragraphs
 * @param {object} options
 * @returns {object[]}
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
 * Write a native table after measuring every cell. values is a cell matrix; box uses inches.
 * weights controls proportional widths; padding uses inches; rowStyles/cellStyles customize
 * rows/cells; cellTexts overrides individual row.column text before fitting.
 * pptx exposes native options. Return effective column widths/row heights.
 * measured sums minimum height; distribute extra box height across rows. Disable automatic
 * pagination to preserve slide count.
 *
 * @param {Canvas} c
 * @param {string} id
 * @param {string[][]} values
 * @param {object} box
 * @param {object} options
 * @returns {{widths:number[],heights:number[]}}
 */
export function table(c, id, values, box, options = {}) {
  const o = c.options('table', id, {
    weights: Array(values[0].length).fill(1), fontSize: 10,
    minFontSize: 7, padding: 0.045, headerFill: c.theme.colors.primary,
    headerColor: c.theme.colors.paper, header: true, ...options,
  });
  values = o.values ?? values;
  if (o.cellTexts) values = values.map((row, r) => row.map((value, col) => o.cellTexts[`${r}.${col}`] ?? value));
  if (o.visible === false) return { widths: [], heights: [] };
  const b = { ...box, ...o.box };
  const sum = o.weights.reduce((a, b) => a + b, 0);
  const widths = o.weights.map(w => b.w * w / sum);
  let size = o.fontSize, heights;
  /**
   * Merge row and cell styles with the cell taking precedence.
   */
  const rowStyle = (r, col) => merge(o.rowStyles?.[r] || {}, o.cellStyles?.[`${r}.${col}`] || {});
  /**
   * Compute each row's minimum height from its tallest cell.
   */
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
 * Reflow a collection and invoke each item renderer in reading order. id prefixes child IDs
 * with .0, .1 and so on. items holds content; box is total space. minWidth/gap use inches;
 * minColumnSpan binds to the grid. render receives (item, box, id, options). Do not reorder
 * or mutate input.
 *
 * @param {Canvas} c
 * @param {string} id
 * @param {object[]} items
 * @param {object} box
 * @param {object} options
 * @param {Function} render
 * @returns {void}
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
 * Compose a frame and heading band, then return the usable panel area. id prefixes
 * frame/bar/title elements; box is the outer area; title is the band text. headingRatio is a
 * height fraction and padding uses inches. frame/bar/title accept separate styles.
 *
 * @param {Canvas} c
 * @param {string} id
 * @param {object} box
 * @param {string} title
 * @param {object} options
 * @returns {object}
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
 * Create a native doughnut with an extra white point forming the hidden semicircle. series
 * contains labels/values; the last value is a spacer rather than a metric. box is the
 * physical chart area. holeSize, firstSliceAng, series and pptx are configurable. Return the
 * effective series after overrides to synchronize labels.
 *
 * @param {Canvas} c
 * @param {string} id
 * @param {object} series
 * @param {object} box
 * @param {object} options
 * @returns {object}
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
 * Split a region between a heading and body without a decorative background. id prefixes
 * heading/body; title is the label; body is text or runs. box is the total region;
 * titleRatio sets the split and heading/body supply overrides. Measure and fit the two text
 * areas independently.
 *
 * @param {Canvas} c
 * @param {string} id
 * @param {string} title
 * @param {string|object[]} body
 * @param {object} box
 * @param {object} options
 * @returns {void}
 */
export function labelBody(c, id, title, body, box, options = {}) {
  const o = c.options('labelBody', id, { titleRatio: 0.18, titleFontSize: 10,
    fontSize: 10, ...options });
  const areas = split({ ...box, ...o.box }, [o.titleRatio, 1 - o.titleRatio], 'y', 0.04);
  c.text(`${id}.heading`, title, areas[0], { fontSize: o.titleFontSize,
    bold: true, color: o.color ?? c.theme.colors.text, ...o.heading });
  c.text(`${id}.body`, body, areas[1], { fontSize: o.fontSize, ...o.body });
}
