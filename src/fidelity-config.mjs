/**
 * Documented fidelity-mode contract. Importing this file does not apply settings.
 * Examples modify the presentation; the configuration without overrides is the
 * reference for visual equality.
 *
 * @typedef {{x:number,y:number,w:number,h:number}} NativeBox Slide inches.
 * @typedef {{x:number,y:number,w:number,h:number}} LocalBox Parent-space EMU (914400/in).
 * @typedef {{col:number,row:number,colSpan:number,rowSpan:number}} GridPlacement
 * Zero-based tracks may be fractional; slide dimensions remain 16:9.
 *
 * @typedef {Object} TextStyle
 * @property {string} [fontFace] Exact installed font name.
 * @property {number} [fontSize] Positive size in points.
 * @property {boolean} [bold] Materialize bold styling in runs.
 * @property {boolean} [italic] Materialize italic styling.
 * @property {string} [color] Six-character sRGB color without #.
 * @property {'left'|'center'|'right'|'justify'} [align] Paragraph alignment.
 * @property {number} [margin] Equal internal margins in inches.
 * @property {'top'|'middle'|'bottom'} [vertical] Vertical anchor.
 * @property {boolean} [wrap] Automatic wrapping in the text body.
 *
 * @typedef {Object} TablePatch
 * @property {string[][]} [rows] Replace values while retaining columns. New rows
 * clone the last row and redistribute the original total height proportionally.
 * @property {Object.<string,object>} [cells] Zero-based row.column keys whose values
 * accept text, fill and textStyle without losing neighboring styles.
 * @property {number[]} [columnWidths] One positive width per column in inches.
 * @property {number[]} [rowHeights] One positive height per row in inches.
 *
 * @typedef {Object} ChartPatch
 * @property {object[]} [series] One entry per series; {} preserves a series. Entries
 * accept name, labels, values, xValues and yValues according to chart type. Preserve
 * point counts and synchronize XML/XLSX, cloning per instance to isolate other slides.
 * @property {object[]} [xmlPatches] Change axes, colors, formats and legends directly
 * in chart XML using XmlOperation syntax.
 *
 * @typedef {Object} XmlOperation
 * @property {string} path XPath relative to the object/part root; uses a:, p:, c:.
 * @property {Object.<string,string|number>} [attributes] Attributes to replace.
 * @property {string} [text] Selected node's text content.
 * @property {boolean} [remove] Remove a node; the root cannot be removed.
 * @property {string} [appendXml] XML fragment with complete namespace declarations.
 *
 * @typedef {Object} ElementPatch
 * @property {string} [text] Replace the body using its first style as a base.
 * @property {Object.<string,string>} [textRuns] Edit runs by index, retaining each
 * existing run's emphasis and style.
 * @property {Object.<string,string>} [textReplacements] Replace text within each run;
 * matches never cross run boundaries or erase mixed formatting.
 * @property {TextStyle} [textStyle] Explicit text styling.
 * @property {NativeBox} [box] Move/resize on the slide; groups retain children.
 * @property {LocalBox} [localBox] Exact control in a group's internal space.
 * @property {GridPlacement} [grid] Position using the current grid.
 * @property {string} [fill] Solid shape fill.
 * @property {{color?:string,width?:number}} [line] Color and width in points.
 * @property {number} [rotation] Rotation in degrees, converted to DrawingML.
 * @property {boolean} [visible] false removes the output object, leaving source intact.
 * @property {TablePatch} [table] Native table configuration.
 * @property {ChartPatch} [chart] Native chart configuration.
 * @property {string|{path:string,fallback:string}} [image] Relative/absolute file path.
 * The JS build automatically creates a PNG compatibility fallback for SVG files.
 * @property {string} [shapeType] DrawingML preset (rect, ellipse, chevron, etc.).
 * @property {string} [name] Name in PowerPoint's selection pane.
 * @property {XmlOperation[]} [xmlPatches] Advanced properties not exposed above.
 *
 * @typedef {Object} FidelityConfig
 * @property {object} [grid] Integer columns/rows; gapX/Y and marginX/Y in inches.
 * @property {object} [theme] Token-based colors/fonts; value-based colorMap/fontMap.
 * Lexical changes apply to DrawingML and do not recolor image pixels.
 * @property {Object.<string,object>} [masters] Catalog slideMasterN keys.
 * @property {Object.<string,object>} [templates] Catalog slideLayoutN keys.
 * @property {Object.<string,object>} [slides] Original slide numbers. Slides accept
 * elements, flows, background and hidden; layouts/masters accept elements/background.
 * @property {Object.<string,ElementPatch>} [elements] slide.eID keys override
 * slides.<n>.elements; for example, 5.e5.
 * @property {Object.<string,object[]>} [additions] New PptxGenJS text/shape objects
 * per slide, with id, kind, text/type, box or grid, and native style options.
 * @property {number[]} [selection] Subset/order without duplicate slide numbers.
 * @property {Object.<string,XmlOperation[]>} [nativeParts] Escape hatch keyed by an
 * existing OPC part name, such as ppt/charts/chart24.xml; applied after slide patches.
 */

/**
 * Working example; it has no effect until passed to build().
 *
 * @type {FidelityConfig}
 */
export const documentedFidelityExample = {
  grid: { columns: 14, rows: 9, gapX: 0, gapY: 0 },
  // Without overrides, the baseline retains all 71 slides and every visual part.
  selection: [5, 10, 50, 68],
  elements: {
    // Actual ID: slide 5 title; other e5 IDs belong to different scenes.
    '5.e5': { text: 'Configured executive summary', textStyle: { fontSize: 19 } },
  },
  slides: {
    10: { elements: { e8: { table: { cells: { '1.2': { text: 'New meeting' } } } } } },
    68: { hidden: false, elements: {
      // The fourth value preserves the invisible semicircle spacer.
      e114: { chart: { series: [{ values: [2, 7, 2, 11] }] } },
    } },
  },
  additions: {
    50: [{ id: 'review-note', kind: 'text', text: 'Review note',
      grid: { col: 1, row: 8, colSpan: 10, rowSpan: 0.5 },
      style: { fontSize: 8, color: 'EC111A' } }],
  },
};
