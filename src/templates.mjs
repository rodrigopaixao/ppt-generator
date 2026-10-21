/**
 * Seven initial semantic responsive templates. They compose new objects and intentionally
 * reflow content. For full fidelity across all 71 slides, use generate.mjs and the native
 * data/slides catalog.
 *
 * @module templates
 */
import { Grid, inset, relative, split } from './layout.mjs';
import { merge } from './theme.mjs';
import { collection, table, panel, donut, richParagraphs, labelBody } from './components.mjs';

/**
 * Resolve header, body and footer from the configurable grid. config is validated by
 * configure. s supplies physical margins; h/f are track spans; the body uses the remaining
 * tracks.
 *
 * @param {object} config
 * @returns {{grid:Grid,header:object,body:object,footer:object}}
 */
export function regions(config) {
  const { width, height } = config.slide;
  const s = config.theme.spacing;
  const grid = new Grid({ x: s.marginX, y: s.marginY,
    w: width - 2 * s.marginX, h: height - 2 * s.marginY }, config.grid);
  const h = config.template.headerRows, f = config.template.footerRows;
  return { grid,
    header: grid.cell(0, 0, grid.columns, h),
    body: grid.cell(0, h, grid.columns, grid.rows - h - f),
    footer: grid.cell(0, grid.rows - f, grid.columns, f) };
}

/**
 * Register PptxGenJS masters/layouts with a background and static chrome. pptx is the
 * library instance; config supplies tokens and templates.<name> overrides; assets holds
 * prepared images and dimensions. Define reusable layouts linked to the exported master.
 * local merges defaults/overrides and objects collects extra static elements.
 *
 * @param {object} pptx
 * @param {object} config
 * @param {object} assets
 * @returns {void}
 */
export function registerMasters(pptx, config, assets) {
  for (const name of Object.keys(templates)) {
    const overrides = config.templates[name] || {};
    const local = merge(config, { template: overrides });
    const { footer } = regions(local);
    const objects = structuredClone(overrides.masterObjects || []);
    if (local.template.showLogo) {
      const logo = assets[overrides.logo || 'assets/logo.svg'];
      const h = Math.min(0.26, footer.h * 0.85), w = h * logo.width / logo.height;
      objects.push({ image: { path: logo.path, x: footer.x + footer.w - w,
        y: footer.y + footer.h - h, w, h } });
    }
    pptx.defineSlideMaster({ title: name, background: { color: local.theme.colors.paper },
      objects, ...(overrides.master || {}) });
  }
}

/**
 * Draw shared elements that vary per slide instance. c is the drawing context; data supplies
 * title, kicker/tags, sourceNumber and footnote; region comes from regions. Titles, labels
 * and page numbers remain editable; the logo lives on the master. runs separates the red
 * topic from its message; t controls visibility and styles.
 *
 * @param {Canvas} c
 * @param {object} data
 * @param {object} region
 * @returns {void}
 */
export function chrome(c, data, region) {
  const { header, footer } = region, { colors, fonts, type } = c.theme;
  const t = c.config.template;
  if (data.tags) {
    let x = header.x;
    data.tags.forEach((tag, i) => {
      const w = Math.min(header.w / data.tags.length, 0.18 + tag.length * 0.075);
      const box = { x, y: header.y, w, h: 0.20 };
      c.shape(`header.tag.${i}.fill`, box, { fill: { color: i ? colors.border : colors.primary },
        line: { color: i ? colors.border : colors.primary } });
      c.text(`header.tag.${i}.text`, tag, inset(box, 0.025), { fontSize: type.kicker,
        color: i ? colors.text : colors.paper, bold: true, align: 'center' });
      x += w;
    });
  } else if (data.kicker) {
    c.text('header.kicker', data.kicker, relative(header, 0, 0, 0.86, 0.23), {
      fontSize: type.kicker, charSpacing: 1.8, color: colors.primary });
  }
  const title = data.title.split('|');
  const runs = title.length > 1 ? [
    { text: title.shift().trim() + ' | ', options: { color: colors.primary } },
    { text: title.join('|').trim(), options: { color: colors.text } },
  ] : data.title;
  c.text('header.title', runs, relative(header, 0, 0.32, 0.985, 0.65), {
    fontFace: fonts.heading, fontSize: type.title, minFontSize: 15,
    ...t.header });
  if (t.showNumber) c.text('header.number', String(data.sourceNumber ?? c.number), {
    x: header.x + header.w - 0.25, y: header.y, w: 0.25, h: 0.18,
  }, { fontSize: type.caption, align: 'right' });
  if (data.footnote) c.text('footer.source', data.footnote,
    relative(footer, 0, 0.04, 0.96, 0.92), { fontSize: type.caption,
      minFontSize: 5.5, ...t.footer });
  if (t.showGrid) {
    const g = region.grid;
    for (let r = 0; r < g.rows; r++) for (let col = 0; col < g.columns; col++)
      c.shape(`debug.grid.${r}.${col}`, g.cell(col, r), {
        line: { color: '00AACC', transparency: 75, width: 0.25 },
        fill: { color: 'FFFFFF', transparency: 100 } });
  }
}

/**
 * Executive-summary template retaining paragraphs and emphasis in a fitted rich-text body.
 * data contains extracted paragraphs without automatic summarization. box is usable body
 * space in inches; o supplies font limits. Canvas rejects impossible overflow.
 *
 * @param {Canvas} c
 * @param {object} data
 * @param {object} box
 * @returns {void}
 */
function executiveSummary(c, data, box) {
  const o = c.options('executiveSummary', 'summary', { fontSize: 10.25, minFontSize: 8 });
  c.text('summary.content', richParagraphs(data.paragraphs, { headingColor: c.theme.colors.primary }), box, {
    ...o, paraSpaceAfter: 3, leading: 1.12 });
}

/**
 * Agenda template using a native table with proportional widths. data.rows is the complete
 * matrix including its header; box is the body region. rowStyles highlights breaks/transfers
 * without omitting rows.
 *
 * @param {Canvas} c
 * @param {object} data
 * @param {object} box
 * @returns {void}
 */
function agenda(c, data, box) {
  const rowStyles = {};
  data.rows.forEach((row, i) => {
    if (/^(Break|Transfer|Free time|OPTIONAL)/i.test(row[2]))
      rowStyles[i] = { fill: c.theme.colors.surface };
  });
  table(c, 'agenda.table', data.rows, box, {
    weights: [1.05, 0.55, 4.05, 1.15, 2.15, 3.4], align: 'left',
    fontSize: 9, minFontSize: 6.75, padding: 0.035, rowStyles });
}

/**
 * Align logos with comparison columns and highlight the bank column. data.logos/rows carry
 * source evidence and box defines the body. areas splits logos/table; columns shares table
 * weights; cellStyles customizes cells without converting them to images.
 *
 * @param {Canvas} c
 * @param {object} data
 * @param {object} box
 * @returns {void}
 */
function competitiveComparison(c, data, box) {
  const areas = split(box, [0.11, 0.89], 'y', 0.03);
  const weights = [1.4, 1, 1, 1, 1, 1, 1];
  const columns = split(areas[0], weights, 'x', 0);
  data.logos.forEach((logo, i) => c.image(`banks.${i}.logo`, logo,
    inset(columns[i + 1], { left: 0.15, right: 0.15, top: 0.04, bottom: 0.04 })));
  const rowStyles = { 0: { fill: c.theme.colors.paper, italic: true },
    8: { fill: c.theme.colors.surface } };
  const cellStyles = {};
  data.rows.forEach((_, row) => {
    cellStyles[`${row}.0`] = { bold: true, align: 'left' };
    cellStyles[`${row}.1`] = { fill: c.theme.colors.surface };
  });
  table(c, 'comparison.table', data.rows, areas[1], {
    weights, fontSize: 9.5, minFontSize: 7, padding: 0.06,
    header: false, rowStyles, cellStyles });
  const sbm = columns[1];
  c.shape('comparison.highlight', { x: sbm.x, y: box.y, w: sbm.w, h: box.h }, {
    line: { color: c.theme.colors.primary, width: 0.8 } });
}

/**
 * Compose mission, pillar collection and expected outcome. data supplies mission, outcome
 * and pillars[{title, icon}]; box is the total region. bands reserves upper/lower strips;
 * collection determines capacity and wraps when necessary. o contains configurable ratios,
 * padding, gaps and minimums.
 *
 * @param {Canvas} c
 * @param {object} data
 * @param {object} box
 * @returns {void}
 */
function strategicPillars(c, data, box) {
  const o = c.options('strategicPillars', 'pillars', { bandRatio: 0.11, padding: 0.38,
    gap: 0.24, minWidth: 2.2, minColumnSpan: 3, fontSize: 19, iconRatio: 0.20 });
  const bands = split(box, [o.bandRatio, 1 - 2 * o.bandRatio, o.bandRatio], 'y', 0);
  for (const [i, text] of [data.mission, data.outcome].entries()) {
    const band = bands[i ? 2 : 0];
    c.shape(`pillars.band.${i}`, band, { fill: { color: c.theme.colors.primary },
      line: { color: c.theme.colors.primary } });
    c.text(`pillars.band.${i}.text`, text, inset(band, 0.08), {
      fontSize: 13, bold: true, color: c.theme.colors.paper, align: 'center', valign: 'mid' });
  }
  c.shape('pillars.left', { x: box.x, y: bands[1].y, w: 0.28, h: bands[1].h }, {
    fill: { color: c.theme.colors.primary }, line: { color: c.theme.colors.primary } });
  c.shape('pillars.right', { x: box.x + box.w - 0.28, y: bands[1].y, w: 0.28, h: bands[1].h }, {
    fill: { color: c.theme.colors.primary }, line: { color: c.theme.colors.primary } });
  collection(c, 'pillars.items', data.pillars, inset(bands[1], o.padding), o, (item, b, id) => {
    c.shape(`${id}.background`, b, { fill: { color: c.theme.colors.surface },
      line: { color: c.theme.colors.neutral, width: 0.7 } });
    const inner = inset(b, 0.18);
    c.image(`${id}.icon`, item.icon, relative(inner, 0.3, 0.12, 0.4, o.iconRatio));
    c.text(`${id}.title`, item.title, relative(inner, 0.02, 0.40, 0.96, 0.50), {
      fontSize: o.fontSize, minFontSize: 12, bold: true, align: 'center' });
  });
}

/**
 * Distribute journey lanes, steps and connections without distorting icons. data.journeys
 * supplies labels, descriptions and steps per lane; box is the total area. rows splits
 * lanes; label/steps separates context and process; diameter preserves circles. Connect only
 * adjacent items on the same visual row.
 *
 * @param {Canvas} c
 * @param {object} data
 * @param {object} box
 * @returns {void}
 */
function clientJourney(c, data, box) {
  const o = c.options('clientJourney', 'journey', { labelWeight: 1.6, contentWeight: 10,
    gap: 0.12, minStepWidth: 1.3, iconRatio: 0.25, fontSize: 9 });
  const [lanes, discussion] = split(box, [0.92, 0.08], 'y', 0.12);
  const rows = split(lanes, data.journeys.map(() => 1), 'y', 0.18);
  data.journeys.forEach((journey, row) => {
    const [label, steps] = split(rows[row], [o.labelWeight, o.contentWeight], 'x', 0.18);
    c.shape(`journey.${row}.label.fill`, label, { fill: { color: c.theme.colors.surface },
      line: { color: c.theme.colors.surface } });
    labelBody(c, `journey.${row}.label`, journey.title, journey.description,
      inset(label, 0.14), { titleRatio: 0.48, titleFontSize: 11.5, fontSize: 10 });
    collection(c, `journey.${row}.steps`, journey.steps, steps, {
      minWidth: o.minStepWidth, gap: o.gap, minColumnSpan: 2,
    }, (step, b, id) => {
      const color = step.accent ? c.theme.colors.primary : c.theme.colors.text;
      const diameter = Math.min(b.w * 0.46, b.h * o.iconRatio);
      const iconBox = { x: b.x + (b.w - diameter) / 2, y: b.y + b.h * 0.18,
        w: diameter, h: diameter };
      c.shape(`${id}.circle`, iconBox, { type: 'ellipse',
        fill: { color: step.accent ? c.theme.colors.primary : c.theme.colors.surface },
        line: { color: step.accent ? c.theme.colors.primary : c.theme.colors.surface } });
      c.image(`${id}.icon`, step.icon, inset(iconBox, 0.06));
      const assisted = step.accent || step.title === 'VIRTUAL / BRANCH';
      c.text(`${id}.channel`, step.channel || (assisted ? 'Virtual / In-person Support' : 'Digital Self-Serve (Mobile / Web)'),
        relative(b, 0.02, 0, 0.96, 0.15), { fontSize: 7.5, italic: true, align: 'center',
          color: assisted ? c.theme.colors.primary : c.theme.colors.muted });
      c.text(`${id}.title`, step.title, relative(b, 0, 0.47, 1, 0.17), {
        fontSize: o.fontSize, bold: true, color, align: 'center' });
      c.text(`${id}.description`, step.description, relative(b, 0.01, 0.66, 0.98, 0.32), {
        fontSize: o.fontSize, color, align: 'center', minFontSize: 7 });
    });
    // Connect only adjacent steps in the same responsive row, behind the text/icon content.
    const stepRecords = c.records.filter(r => r.id.startsWith(`journey.${row}.steps.`) && r.id.endsWith('.circle'));
    stepRecords.forEach((r, i) => {
      const next = stepRecords[i + 1];
      if (next && Math.abs(next.box.y - r.box.y) < 0.02)
        c.line(`journey.${row}.connector.${i}`, r.box.x + r.box.w + 0.04,
          r.box.y + r.box.h / 2, next.box.x - 0.04, next.box.y + next.box.h / 2,
          { endArrowType: 'triangle', width: 0.7 });
    });
    if (!row) c.line('journey.separator', box.x, rows[row].y + rows[row].h + 0.09,
      box.x + box.w, rows[row].y + rows[row].h + 0.09, { dashType: 'dash' });
  });
  c.shape('journey.discussion.frame', discussion, { line: { color: c.theme.colors.primary, width: 0.8 } });
  c.text('journey.discussion.text', data.discussion, inset(discussion, 0.04), {
    fontSize: 9.5, bold: true, align: 'center', valign: 'mid' });
}

/**
 * Compose execution panels with health, doughnut charts, accomplishments and concerns.
 * data.pillars supplies headings, five status values and chart series. box is the total
 * region; metrics/achievements/concerns are proportional areas. effectiveSeries synchronizes
 * displayed values with overrides.
 *
 * @param {Canvas} c
 * @param {object} data
 * @param {object} box
 * @returns {void}
 */
function executionDashboard(c, data, box) {
  const o = c.options('executionDashboard', 'dashboard', { gap: 0.30, minWidth: 3.25, minColumnSpan: 4,
    fontSize: 10.5, chartFontSize: 8 });
  const status = ['Major Issues', 'At Risk', 'On Track', 'Not Started', 'Completed'];
  const colors = ['majorIssues', 'atRisk', 'onTrack', 'neutral', 'complete'].map(key => c.theme.colors[key]);
  collection(c, 'dashboard.pillars', data.pillars, box, o, (item, b, id) => {
    const body = panel(c, id, b, item.title, { headingRatio: 0.065, padding: 0.16,
      headingFontSize: 11 });
    const [metrics, achievements, concerns] = split(body, [0.34, 0.33, 0.33], 'y', 0.13);
    const [health, chart] = split(metrics, [0.39, 0.61], 'x', 0.12);
    c.text(`${id}.health.title`, 'Initiative health', relative(health, 0, 0, 1, 0.15), {
      bold: true, italic: true, fontSize: 10 });
    const statusBox = relative(health, 0, 0.21, 1, 0.78);
    const statusRows = split(statusBox, status.map(() => 1), 'y', 0.015);
    statusRows.forEach((r, i) => {
      c.text(`${id}.health.${i}.value`, String(item.health[i]), relative(r, 0, 0, 0.12, 1), {
        bold: true, fontSize: 10.5 });
      const dot = relative(r, 0.20, 0.18, 0.10, 0.55);
      const diameter = Math.min(dot.w, dot.h);
      c.shape(`${id}.health.${i}.dot`, { ...dot, w: diameter, h: diameter }, {
        type: 'ellipse', fill: { color: colors[i] }, line: { color: colors[i] } });
      c.text(`${id}.health.${i}.label`, status[i], relative(r, 0.37, 0, 0.63, 1), {
        fontSize: 8, minFontSize: 6.5 });
    });
    c.line(`${id}.metrics.separator`, health.x + health.w + 0.06, metrics.y,
      health.x + health.w + 0.06, metrics.y + metrics.h, { dashType: 'dash' });
    c.text(`${id}.chart.title`, 'Work package completion', relative(chart, 0, 0, 1, 0.16), {
      bold: true, italic: true, fontSize: 9.5, align: 'center' });
    const effectiveSeries = donut(c, `${id}.chart`, item.chart, relative(chart, 0.01, 0.18, 0.98, 0.74));
    // Three source values; the fourth is a hidden half-ring spacer, never a metric.
    c.text(`${id}.chart.values`, effectiveSeries.values.slice(0, 3).join('   /   '),
      relative(chart, 0.05, 0.68, 0.9, 0.16), { fontSize: o.chartFontSize, align: 'center' });
    c.text(`${id}.chart.legend`, effectiveSeries.labels.slice(0, 3).join('   '), relative(chart, 0, 0.85, 1, 0.15), {
      fontSize: 6.5, minFontSize: 6, color: c.theme.colors.muted, align: 'center' });
    for (const [kind, paragraphs, area] of [
      ['accomplishments', item.accomplishments, achievements], ['concerns', item.concerns, concerns],
    ]) {
      const title = paragraphs[0].text;
      labelBody(c, `${id}.${kind}`, title, richParagraphs(paragraphs.slice(1), {
        headingColor: c.theme.colors.primary }), area, {
        titleRatio: 0.18, titleFontSize: 11, fontSize: o.fontSize,
        body: { minFontSize: 8, leading: 1.14, paraSpaceAfter: 3 } });
    }
  });
}

/**
 * Compose the calendar, events, availability and committees in chronological order. data
 * supplies ISO start/end, months/weeks, milestones, availability, committees and legend
 * independently of layout. box is available space. bands defines strips; lanes separates
 * nearby labels; cards reflow while milestones use actual dates as horizontal anchors.
 *
 * @param {Canvas} c
 * @param {object} data
 * @param {object} box
 * @returns {void}
 */
function timeline(c, data, box) {
  const o = c.options('timeline', 'timeline', { labelRatio: 0.13, fontSize: 7,
    lanes: 4, gap: 0.10, committeeMinWidth: 1.7 });
  const bands = split(box, [0.10, 0.31, 0.15, 0.38, 0.06], 'y', 0.035);
  /**
   * Split a band between its left label and chronological content on the right.
   */
  const splitBand = b => split(b, [o.labelRatio, 1 - o.labelRatio], 'x', 0.08);
  const [, calendar] = splitBand(bands[0]);
  const monthBoxes = split(relative(calendar, 0, 0, 1, 0.5), data.months.map(m => m.weeks), 'x', 0);
  monthBoxes.forEach((b, i) => {
    c.shape(`timeline.month.${i}.frame`, b, {});
    c.text(`timeline.month.${i}.text`, data.months[i].label, inset(b, 0.025), {
      fontSize: 9, bold: true, align: 'center' });
  });
  split(relative(calendar, 0, 0.5, 1, 0.5), data.weeks.map(() => 1), 'x', 0).forEach((b, i) => {
    c.shape(`timeline.week.${i}.frame`, b, {});
    c.text(`timeline.week.${i}.text`, data.weeks[i], inset(b, 0.025), { fontSize: 8, align: 'center' });
  });
  /**
   * Convert an ISO date to a 0..1 interval fraction independently of local time zone.
   */
  const dateRatio = date => Math.max(0, Math.min(1,
    (Date.parse(date) - Date.parse(data.start)) / (Date.parse(data.end) - Date.parse(data.start))));
  /**
   * Position events by date within lanes. ordered sorts each lane; left/right bound
   * neighboring events; labelWidth limits label width while anchor remains tied to the correct
   * date.
   */
  const renderEvents = (id, events, target, lanes) => {
    const laneBoxes = split(target, Array(lanes).fill(1), 'y', 0.02);
    for (let lane = 0; lane < lanes; lane++) {
      const ordered = events.map((event, index) => ({ ...event, index }))
        .filter((event, i) => (event.lane ?? i % lanes) === lane)
        .sort((a, b) => Date.parse(a.date) - Date.parse(b.date));
      ordered.forEach((event, j) => {
        const b = laneBoxes[lane], anchor = target.x + dateRatio(event.date) * target.w;
        // Labels are constrained by midpoints between adjacent events in the same lane.
        const prev = ordered[j - 1], next = ordered[j + 1];
        const left = prev ? (anchor + target.x + dateRatio(prev.date) * target.w) / 2 : target.x;
        const right = next ? (anchor + target.x + dateRatio(next.date) * target.w) / 2 : target.x + target.w;
        const labelWidth = Math.min(o.labelWidth ?? 1.3, right - left - 0.05);
        const label = { x: Math.max(left + 0.025, Math.min(anchor - labelWidth / 2,
          right - labelWidth - 0.025)), y: b.y + 0.10, w: labelWidth, h: b.h - 0.10 };
        const color = event.kind === 'board' ? c.theme.colors.neutral :
          event.kind === 'review' ? c.theme.colors.border : c.theme.colors.complete;
        const marker = { x: Math.min(target.x + target.w - 0.065, Math.max(target.x, anchor - 0.0325)),
          y: b.y, w: 0.065, h: 0.065 };
        c.shape(`${id}.${event.index}.marker`, marker, {
          type: event.kind === 'meeting' || event.kind === 'board' || id === 'timeline.availability' ? 'triangle' : 'ellipse',
          fill: { color }, line: { color } });
        if (event.end) {
          const end = target.x + dateRatio(event.end) * target.w;
          c.line(`${id}.${event.index}.duration`, anchor, b.y + 0.035, end, b.y + 0.035,
            { color, width: 3 });
        }
        c.text(`${id}.${event.index}.label`, event.label, label, {
          fontSize: o.fontSize, minFontSize: 5.75, align: 'center' });
      });
    }
  };
  for (const [i, heading] of [[1, 'Key milestones'], [2, 'Content availability'],
    [3, 'Proposed Steering Committee Dates & Topics']]) {
    const [label, target] = splitBand(bands[i]);
    c.text(`timeline.band.${i}.heading`, heading, inset(label, 0.04), {
      fontSize: 9, bold: true, color: c.theme.colors.primary, valign: 'mid' });
    if (i === 1) renderEvents('timeline.milestones', data.milestones, target, o.lanes);
    if (i === 2) renderEvents('timeline.availability', data.availability, target, 1);
    if (i === 3) collection(c, 'timeline.committees', data.committees, target, {
      minWidth: o.committeeMinWidth, gap: o.gap, minColumnSpan: 2,
    }, (item, b, id) => {
      c.shape(`${id}.frame`, b, { fill: { color: c.theme.colors.surface },
        line: { color: c.theme.colors.primary, width: 0.6 } });
      const [date, title, ...body] = item.text.trim().split('\n').filter(Boolean);
      const inner = inset(b, 0.075);
      c.text(`${id}.date`, date, relative(inner, 0, 0, 1, 0.15), {
        color: c.theme.colors.primary, bold: true, italic: true, fontSize: 7.5 });
      c.text(`${id}.title`, title, relative(inner, 0, 0.17, 1, 0.16), {
        bold: true, fontSize: 8 });
      c.text(`${id}.body`, body.join('\n'), relative(inner, 0, 0.35, 1, 0.65), {
        fontSize: 7.5, minFontSize: 6, leading: 1.12 });
      // Date anchors preserve scheduling semantics while cards read in chronological order.
      const anchorX = calendar.x + dateRatio(item.date) * calendar.w;
      c.shape(`${id}.anchor`, { x: anchorX - 0.032, y: bands[1].y - 0.03, w: 0.064, h: 0.064 }, {
        type: 'ellipse', fill: { color: c.theme.colors.primary }, line: { color: c.theme.colors.primary } });
    });
  }
  const [, legend] = splitBand(bands[4]);
  const legendLabels = data.legend || ['Board Submissions', 'Group Head Review', 'Key Content Dates', 'Steering Committee Meetings'];
  const legendColors = [c.theme.colors.neutral, c.theme.colors.border, c.theme.colors.complete, c.theme.colors.primary];
  split(legend, legendLabels.map(() => 1), 'x', 0.08).forEach((b, i) => {
    const marker = { x: b.x, y: b.y + b.h * 0.30, w: 0.08, h: 0.08 };
    c.shape(`timeline.legend.${i}.marker`, marker, {
      type: i === 0 || i === 2 ? 'triangle' : 'ellipse',
      fill: { color: legendColors[i] }, line: { color: legendColors[i] } });
    c.text(`timeline.legend.${i}.text`, legendLabels[i], {
      x: b.x + 0.12, y: b.y, w: b.w - 0.12, h: b.h }, {
      fontSize: 7, color: c.theme.colors.muted, valign: 'mid' });
  });
  if (data.disclaimer) c.text('timeline.disclaimer', data.disclaimer,
    { x: box.x + box.w * 0.72, y: c.theme.spacing.marginY, w: box.w * 0.28 - 0.35, h: 0.14 }, {
      fontSize: 6.5, italic: true, color: c.theme.colors.primary, align: 'right' });
}

export const templates = {
  executiveSummary, agenda, timeline, competitiveComparison,
  strategicPillars, clientJourney, executionDashboard,
};

/**
 * Resolve the template instance, draw chrome and delegate its body. data requires
 * template/title and the family-specific content. overrides changes shared structure by
 * template name; r holds physical regions; render is the registered function. Unknown
 * template names are configuration errors.
 *
 * @param {Canvas} c
 * @param {object} data
 * @returns {void}
 */
export function renderTemplate(c, data) {
  const overrides = c.config.templates[data.template] || {};
  c.config = merge(c.config, { template: overrides });
  const r = regions(c.config);
  chrome(c, data, r);
  const render = templates[data.template];
  if (!render) throw new Error(`Unknown template: ${data.template}`);
  render(c, data, r.body);
}
