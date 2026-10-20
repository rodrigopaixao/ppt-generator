/**
 * Contrato documentado do modo fiel. Este arquivo é código importável, não uma
 * configuração aplicada automaticamente. Os exemplos alteram a apresentação;
 * a configuração padrão sem overrides é a referência para igualdade visual.
 *
 * @typedef {{x:number,y:number,w:number,h:number}} NativeBox Polegadas no slide.
 * @typedef {{x:number,y:number,w:number,h:number}} LocalBox EMU no pai (914400/in).
 * @typedef {{col:number,row:number,colSpan:number,rowSpan:number}} GridPlacement
 * Tracks base zero; frações são permitidas. As dimensões do slide continuam 16:9.
 *
 * @typedef {Object} TextStyle
 * @property {string} [fontFace] Nome exato da fonte instalada.
 * @property {number} [fontSize] Tamanho em pontos, positivo.
 * @property {boolean} [bold] Materializa negrito nos runs.
 * @property {boolean} [italic] Materializa itálico.
 * @property {string} [color] Cor sRGB, seis caracteres, sem #.
 * @property {'left'|'center'|'right'|'justify'} [align] Alinhamento do parágrafo.
 * @property {number} [margin] Margens internas iguais, em polegadas.
 * @property {'top'|'middle'|'bottom'} [vertical] Âncora vertical.
 * @property {boolean} [wrap] Quebra automática de linha no corpo de texto.
 *
 * @typedef {Object} TablePatch
 * @property {string[][]} [rows] Substitui valores. Mantém colunas; linhas novas
 * clonam a última linha e redistribuem a altura total original proporcionalmente.
 * @property {Object.<string,object>} [cells] Chaves "linha.coluna", base zero;
 * valores aceitam text, fill e textStyle. Uma edição não perde os estilos irmãos.
 * @property {number[]} [columnWidths] Uma largura positiva por coluna, em in.
 * @property {number[]} [rowHeights] Uma altura positiva por linha, em in.
 *
 * @typedef {Object} ChartPatch
 * @property {object[]} [series] Uma entrada por série; {} preserva uma série.
 * Cada entrada aceita name, labels, values, xValues e yValues, conforme o tipo
 * de gráfico. A quantidade de pontos é preservada. XML e XLSX são sincronizados
 * e clonados por instância, evitando efeitos em outros slides.
 * @property {object[]} [xmlPatches] Altera eixos, cores, formatos, legendas etc.
 * diretamente no XML do gráfico, com a mesma sintaxe de XmlOperation.
 *
 * @typedef {Object} XmlOperation
 * @property {string} path XPath relativo à raiz do objeto/parte; usa a:, p:, c:.
 * @property {Object.<string,string|number>} [attributes] Atributos a substituir.
 * @property {string} [text] Conteúdo textual do nó selecionado.
 * @property {boolean} [remove] Remove o nó; a raiz não pode ser removida.
 * @property {string} [appendXml] Fragmento XML com namespaces completos.
 *
 * @typedef {Object} ElementPatch
 * @property {string} [text] Substitui o corpo, usando o primeiro estilo como base.
 * @property {Object.<string,string>} [textRuns] Edita runs por índice, preservando
 * as ênfases e estilos de cada run existente.
 * @property {Object.<string,string>} [textReplacements] Substituições dentro de
 * cada run; não cruza fronteiras de runs para não apagar formatação.
 * @property {TextStyle} [textStyle] Estilo explícito de texto.
 * @property {NativeBox} [box] Move/redimensiona no slide; grupos mantêm os filhos.
 * @property {LocalBox} [localBox] Controle exato no espaço interno de um grupo.
 * @property {GridPlacement} [grid] Posiciona com o grid atual.
 * @property {string} [fill] Preenchimento sólido de uma forma.
 * @property {{color?:string,width?:number}} [line] Cor e espessura em pontos.
 * @property {number} [rotation] Rotação em graus; convertida para DrawingML.
 * @property {boolean} [visible] false remove o objeto da saída, sem tocar na fonte.
 * @property {TablePatch} [table] Configuração de uma tabela nativa.
 * @property {ChartPatch} [chart] Configuração de gráfico nativo.
 * @property {string|{path:string,fallback:string}} [image] Arquivo relativo ou
 * absoluto. SVG recebe PNG de compatibilidade automaticamente no build JS.
 * @property {string} [shapeType] Preset DrawingML (rect, ellipse, chevron etc.).
 * @property {string} [name] Nome no painel de seleção do PowerPoint.
 * @property {XmlOperation[]} [xmlPatches] Propriedades avançadas não expostas acima.
 *
 * @typedef {Object} FidelityConfig
 * @property {object} [grid] columns/rows inteiros; gapX/Y e marginX/Y em in.
 * @property {object} [theme] colors/fontes por tokens; colorMap/fontMap por valor.
 * Alterações lexicais aplicam-se a DrawingML, não recolorem pixels de imagens.
 * @property {Object.<string,object>} [masters] Chaves slideMasterN do catálogo.
 * @property {Object.<string,object>} [templates] Chaves slideLayoutN do catálogo.
 * @property {Object.<string,object>} [slides] Números originais. Cada slide aceita
 * elements, flows, background e hidden. Layout/master aceitam elements/background.
 * @property {Object.<string,ElementPatch>} [elements] Chaves "slide.eID". Tem maior
 * precedência que slides.<n>.elements. Ex.: "5.e5".
 * @property {Object.<string,object[]>} [additions] Novos objetos PptxGenJS text/shape
 * por slide. Aceitam id, kind, text/type, box ou grid e style (opções PptxGenJS).
 * @property {number[]} [selection] Subconjunto/ordem sem números repetidos.
 * @property {Object.<string,XmlOperation[]>} [nativeParts] Escape hatch por nome
 * de parte OPC existente, como ppt/charts/chart24.xml. Aplicado depois dos slides.
 */

/** @type {FidelityConfig} Exemplo funcional, sem efeito até ser passado para build(). */
export const documentedFidelityExample = {
  grid: { columns: 14, rows: 9, gapX: 0, gapY: 0 },
  // Sem overrides, o baseline mantém os 71 slides e todas as partes visuais.
  selection: [5, 10, 50, 68],
  elements: {
    // ID real: título do slide 5; outros e5 pertencem a outras cenas.
    '5.e5': { text: 'Configured executive summary', textStyle: { fontSize: 19 } },
  },
  slides: {
    10: { elements: { e8: { table: { cells: { '1.2': { text: 'New meeting' } } } } } },
    68: { hidden: false, elements: {
      // O quarto número conserva o espaço invisível do semicírculo.
      e114: { chart: { series: [{ values: [2, 7, 2, 11] }] } },
    } },
  },
  additions: {
    50: [{ id: 'review-note', kind: 'text', text: 'Review note',
      grid: { col: 1, row: 8, colSpan: 10, rowSpan: 0.5 },
      style: { fontSize: 8, color: 'EC111A' } }],
  },
};
