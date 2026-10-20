/**
 * Geometria independente do PowerPoint. Não escreve arquivos nem desenha assets.
 * @typedef {{x:number,y:number,w:number,h:number}} Box Caixa em polegadas.
 * @typedef {{columns:number,rows:number,gapX:number,gapY:number}} GridOptions
 * Coordenadas de grid usam base zero e aceitam frações. Polegadas e tracks nunca
 * são intercambiados implicitamente. Todo layout rejeita áreas impossíveis.
 */
export class Grid {
  /**
   * Divide box em tracks iguais, descontando intervalos antes da divisão.
   * @param {Box} box Região disponível no canvas.
   * @param {GridOptions} options Quantidade de tracks e gaps em polegadas.
   * cw/rh são largura/altura úteis de cada track; box permanece em coordenadas
   * globais. A validação impede divisões por zero e gaps maiores que a região.
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
   * Resolve uma região do grid para polegadas, incluindo gaps internos ao span.
   * @param {number} col Coluna inicial, base zero.
   * @param {number} row Linha inicial, base zero.
   * @param {number} colSpan Quantidade de colunas, inclusive fracionárias.
   * @param {number} rowSpan Quantidade de linhas.
   * @returns {Box} Caixa física; falha se ultrapassar os limites do grid.
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
   * Distribui itens da esquerda para a direita, continuando na próxima linha.
   * @param {object[]} items Itens com colSpan e rowSpan opcionais.
   * @returns {object[]} Novos itens com box; a lista de entrada não é alterada.
   * col é o cursor horizontal; row é a linha atual; lineHeight guarda a maior
   * altura da linha anterior, evitando sobreposição de itens de spans distintos.
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
 * Desconta padding e desloca a origem para dentro da caixa.
 * @param {Box} box Caixa externa.
 * @param {number|object} pad Polegadas iguais ou {top,right,bottom,left}.
 * @returns {Box} Caixa interna. Campos omitidos valem zero; área vazia falha.
 */
export function inset(box, pad) {
  const p = typeof pad === 'number' ? { top: pad, right: pad, bottom: pad, left: pad } : pad;
  const result = { x: box.x + (p.left || 0), y: box.y + (p.top || 0),
    w: box.w - (p.left || 0) - (p.right || 0), h: box.h - (p.top || 0) - (p.bottom || 0) };
  if (result.w <= 0 || result.h <= 0) throw new Error('Padding consumes component area.');
  return result;
}

/**
 * Divide uma caixa proporcionalmente em uma linha ou coluna.
 * @param {Box} box Espaço a dividir.
 * @param {number[]} weights Pesos positivos, sem obrigação de somar 1.
 * @param {'x'|'y'} axis Direção da distribuição.
 * @param {number} gap Intervalo em polegadas entre regiões.
 * @returns {Box[]} Regiões consecutivas que ocupam exatamente o espaço.
 * available desconta gaps; total normaliza pesos; cursor avança após cada item.
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
 * Reflow de coleção com células iguais, na ordem de leitura.
 * @param {Box} box Região total.
 * @param {number} count Quantidade positiva de itens.
 * @param {object} options minWidth e gap em polegadas; maxColumns limita colunas.
 * @returns {Box[]} Uma caixa por item. Uma última linha incompleta preserva as
 * larguras das colunas para manter alinhamento. cols deriva da largura mínima;
 * rows deriva de count/cols; linhas compartilham igualmente a altura disponível.
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
 * Converte frações de uma caixa pai em coordenadas físicas.
 * @param {Box} box Pai em polegadas.
 * @param {number} x Fração de deslocamento horizontal.
 * @param {number} y Fração de deslocamento vertical.
 * @param {number} w Fração da largura do pai.
 * @param {number} h Fração da altura do pai.
 * @returns {Box} Caixa filha; quem renderiza valida seus limites finais.
 */
export function relative(box, x, y, w, h) {
  return { x: box.x + box.w * x, y: box.y + box.h * y, w: box.w * w, h: box.h * h };
}
