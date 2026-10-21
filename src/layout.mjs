/**
 * Geometry independent of PowerPoint, without file writes or artwork rendering. Box uses
 * inches; GridOptions defines columns, rows and inch-based gaps. Grid coordinates are
 * zero-based and may be fractional. Inches and tracks are never implicitly interchangeable.
 * Reject impossible layout regions.
 *
 * @typedef {{x:number,y:number,w:number,h:number}} Box
 * @typedef {{columns:number,rows:number,gapX:number,gapY:number}} GridOptions
 */
export class Grid {
  /**
   * Divide box into equal tracks after subtracting gaps. box is the available canvas region;
   * options supplies track counts and inch-based gaps. cw/rh are usable track dimensions; box
   * stays in global coordinates. Validation prevents division by zero and gaps larger than the
   * region.
   *
   * @param {Box} box
   * @param {GridOptions} options
   */
  constructor(box, { columns = 14, rows = 9, gapX = 0.12, gapY = 0.1 } = {}) {
    if (!(columns > 0 && rows > 0 && Number.isInteger(columns) && Number.isInteger(rows)))
      throw new Error('Grid columns and rows must be positive integers.');
    if (!(box.w > 0 && box.h > 0 && gapX >= 0 && gapY >= 0))
      throw new Error('Invalid grid dimensions or gaps.');
    Object.assign(this, { box, columns, rows, gapX, gapY });
    this.cw = (box.w - (columns - 1) * gapX) / columns;
    this.rh = (box.h - (rows - 1) * gapY) / rows;
    if (!(this.cw > 0 && this.rh > 0)) throw new Error('Grid gaps exceed available space.');
  }
  /**
   * Resolve a grid region to inches, including internal gaps within its span. col/row are
   * zero-based starts; colSpan/rowSpan may be fractional. Return a physical box and fail if it
   * exceeds grid bounds.
   *
   * @param {number} col
   * @param {number} row
   * @param {number} colSpan
   * @param {number} rowSpan
   * @returns {Box}
   */
  cell(col, row, colSpan = 1, rowSpan = 1) {
    if (col < 0 || row < 0 || colSpan <= 0 || rowSpan <= 0 ||
        col + colSpan > this.columns + 1e-7 || row + rowSpan > this.rows + 1e-7)
      throw new Error('Grid placement exceeds bounds.');
    return { x: this.box.x + col * (this.cw + this.gapX),
      y: this.box.y + row * (this.rh + this.gapY),
      w: colSpan * (this.cw + this.gapX) - this.gapX,
      h: rowSpan * (this.rh + this.gapY) - this.gapY };
  }
  /**
   * Distribute items left to right, continuing on the next row. items may specify
   * colSpan/rowSpan. Return new items with boxes without mutating input. col/row track the
   * cursor; lineHeight retains the previous row's greatest height to prevent overlap between
   * different spans.
   *
   * @param {object[]} items
   * @returns {object[]}
   */
  flow(items) {
    let col = 0, row = 0, lineHeight = 0;
    return items.map(item => {
      const span = item.colSpan ?? 1, height = item.rowSpan ?? 1;
      if (col + span > this.columns) { col = 0; row += lineHeight; lineHeight = 0; }
      const box = this.cell(col, row, span, height);
      col += span; lineHeight = Math.max(lineHeight, height);
      return { ...item, box };
    });
  }
}

/**
 * Subtract padding and move the origin inside the box. box is the outer area; pad is uniform
 * inches or {top, right, bottom, left}. Return the inner box. Missing sides default to zero;
 * empty areas fail.
 *
 * @param {Box} box
 * @param {number|object} pad
 * @returns {Box}
 */
export function inset(box, pad) {
  const p = typeof pad === 'number' ? { top: pad, right: pad, bottom: pad, left: pad } : pad;
  const result = { x: box.x + (p.left || 0), y: box.y + (p.top || 0),
    w: box.w - (p.left || 0) - (p.right || 0), h: box.h - (p.top || 0) - (p.bottom || 0) };
  if (result.w <= 0 || result.h <= 0) throw new Error('Padding consumes component area.');
  return result;
}

/**
 * Split a box proportionally along a row or column. weights are positive and need not sum to
 * one; axis selects x/y; gap uses inches. Return consecutive regions filling the available
 * space. available excludes gaps; total normalizes weights; cursor advances after each item.
 *
 * @param {Box} box
 * @param {number[]} weights
 * @param {'x'|'y'} axis
 * @param {number} gap
 * @returns {Box[]}
 */
export function split(box, weights, axis = 'x', gap = 0.12) {
  if (!weights.length || weights.some(w => !(w > 0)) || !['x', 'y'].includes(axis) || gap < 0)
    throw new Error('Invalid flow weights, axis or gap.');
  const size = axis === 'x' ? 'w' : 'h';
  const available = box[size] - gap * (weights.length - 1);
  if (available <= 0) throw new Error('Flow has no usable space.');
  const total = weights.reduce((a, b) => a + b, 0);
  let cursor = box[axis];
  return weights.map(weight => {
    const cell = { ...box, [axis]: cursor, [size]: available * weight / total };
    cursor += cell[size] + gap;
    return cell;
  });
}

/**
 * Reflow a collection into equal cells in reading order. box is the total region and count
 * is a positive integer. minWidth/gap use inches; maxColumns limits columns. Incomplete
 * final rows retain column widths for alignment. cols derives from minimum width, rows from
 * count/cols; rows share available height equally.
 *
 * @param {Box} box
 * @param {number} count
 * @param {object} options
 * @returns {Box[]}
 */
export function wrap(box, count, { minWidth = 1.8, gap = 0.12, maxColumns = count } = {}) {
  if (!Number.isInteger(count) || count < 1 || !(minWidth > 0) || maxColumns < 1)
    throw new Error('Invalid responsive collection size.');
  const cols = Math.min(count, maxColumns, Math.max(1, Math.floor((box.w + gap) / (minWidth + gap))));
  const rows = Math.ceil(count / cols);
  const lines = split(box, Array(rows).fill(1), 'y', gap);
  return Array.from({ length: count }, (_, i) =>
    split(lines[Math.floor(i / cols)], Array(cols).fill(1), 'x', gap)[i % cols]);
}

/**
 * Convert fractions of a parent box into physical coordinates. box uses inches; x/y are
 * offset fractions and w/h are size fractions. Return a child box whose final bounds are
 * validated by the renderer.
 *
 * @param {Box} box
 * @param {number} x
 * @param {number} y
 * @param {number} w
 * @param {number} h
 * @returns {Box}
 */
export function relative(box, x, y, w, h) {
  return { x: box.x + box.w * x, y: box.y + box.h * y, w: box.w * w, h: box.h * h };
}
