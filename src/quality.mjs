/**
 * Perfil de revisão: recompõe os sete layouts reportados e mantém os demais
 * objetos editáveis. Tokens são pt (fontes), in (geometria) e pt (margem de tabela).
 * quality.elements['slide.id'] substitui qualquer propriedade da declaração
 * gerada; slides/elements nativos continuam disponíveis para o restante do deck.
 */
import fs from 'node:fs';
import path from 'node:path';
import { merge } from './theme.mjs';
import { textHeight, root } from './components.mjs';

export const qualityDefaults = {
  font: 'Arial',
  type: { title: { min: 22, size: 22, max: 24 }, body: { min: 12, size: 12, max: 16 },
    dense: { min: 10, size: 10, max: 12 }, note: { min: 8, size: 8, max: 9 } },
  spacing: { marginX: 0.56, gap: 0.12, padding: 0.08, tablePadding: 2, leading: 1.1 },
  repairSlides: [10, 23, 29, 31, 34, 40, 58, 65], elements: {}, roles: {},
  strict: true, paginationSafety: 1.12,
  fontFit: { enabled: true, step: 0.25 },
  referenceTypography: { enabled: true, elements: {} },
  flow: { enabled:true, boxPadding:0.06, panelPadding:0.12, regions:{
  "35": {
    "calloutRows": [
      {
        "top": 2.39,
        "padding": 0.12,
        "gap": 0.06,
        "rows": [
          {
            "background": "e162",
            "text": "e99",
            "icon": [
              "e161",
              "e172"
            ]
          },
          {
            "background": "e163",
            "text": "e140",
            "icon": [
              "e168",
              "e173"
            ]
          },
          {
            "background": "e164",
            "text": "e146",
            "icon": [
              "e169",
              "e174"
            ]
          },
          {
            "background": "e165",
            "text": "e147",
            "icon": [
              "e170",
              "e175"
            ]
          },
          {
            "background": "e166",
            "text": "e62",
            "icon": [
              "e171",
              "e176"
            ]
          }
        ]
      }
    ],
    "elements": {
      "e102": {
        "box": {
          "y": 5.91,
          "h": 0.16
        },
        "role": "dense",
        "inset": 0
      },
      "e103": {
        "box": {
          "y": 5.91,
          "h": 0.16
        },
        "role": "dense",
        "inset": 0
      },
      "e68": {
        "box": {
          "y": 6.46,
          "h": 0.2
        },
        "role": "dense",
        "inset": 0
      },
      "e72": {
        "box": {
          "y": 6.46,
          "h": 0.2
        },
        "role": "dense",
        "inset": 0
      }
    }
  },
  "47": {
    "elements": {
      "e15": {
        "box": {
          "h": 1.05
        },
        "compact": true,
        "paragraphs": [
          "section",
          "dense"
        ],
        "role": "dense",
        "inset": 0,
        "bottom": 2.91
      },
      "e16": {
        "box": {
          "h": 1.05
        },
        "compact": true,
        "paragraphs": [
          "section",
          "dense"
        ],
        "role": "dense",
        "inset": 0,
        "bottom": 2.91
      },
      "e17": {
        "box": {
          "h": 1.05
        },
        "compact": true,
        "paragraphs": [
          "section",
          "dense"
        ],
        "role": "dense",
        "inset": 0,
        "bottom": 2.91
      },
      "e18": {
        "box": {
          "h": 1.05
        },
        "compact": true,
        "paragraphs": [
          "section",
          "dense"
        ],
        "role": "dense",
        "inset": 0,
        "bottom": 2.91
      },
      "e26": {
        "box": {
          "x": 7.2,
          "y": 5.19,
          "w": 2.47,
          "h": 1.15
        },
        "inset": 0,
        "role": "dense",
        "paragraphGap": 0.04,
        "rich": true
      }
    },
    "numbered": {
      "e26": {
        "ids": [
          "e585",
          "e586",
          "e587"
        ],
        "x": 6.83,
        "lane": 0.24,
        "size": 0.24
      }
    }
  },
  "57": {
    "elements": {
      "e9": {
        "paragraphs": [
          "section",
          "dense"
        ],
        "inset": 0.12,
        "role": "dense",
        "rich": true
      },
      "e18": {
        "box": {
          "h": 4.2
        },
        "bottom": 6.51
      }
    },
    "legends": [
      {
        "right": 9.4,
        "y": 2.02,
        "size": 0.15,
        "gap": 0.08,
        "itemGap": 0.18,
        "items": [
          {
            "marker": "e219",
            "label": "e220"
          },
          {
            "marker": "e222",
            "label": "e223"
          }
        ]
      }
    ]
  },
  "67": {
    "elements": {
      "e13": {
        "box": {
          "h": 4.36
        },
        "paragraphs": [
          "section",
          "dense"
        ],
        "role": "dense",
        "inset": 0.12,
        "rich": true
      },
      "e17": {
        "box": {
          "h": 4.36
        }
      },
      "e7": {
        "box": {
          "x": 0.56,
          "y": 6.23,
          "w": 12.2,
          "h": 0.4
        },
        "inset": 0.06,
        "role": "dense",
        "rich": true
      }
    }
  },
  "70": {
    "elements": {
      "e2": {
        "box": {
          "x": 9.55,
          "y": 2.27,
          "w": 3.21,
          "h": 4.39
        },
        "compact": true,
        "paragraphs": [
          "dense"
        ],
        "inset": 0.12,
        "role": "dense",
        "rich": true
      },
      "e11": {
        "box": {
          "h": 4.34
        },
        "bottom": 6.58,
        "rich": true
      },
      "e4": {
        "compact": true
      }
    }
  },
  "27": {
    "elements": {
      "e18": {
        "paragraphs": [
          "component",
          "dense"
        ],
        "inset": 0.12,
        "role": "dense",
        "rich": true
      }
    }
  }
}, textHierarchy:{
  "24": {
    "e14": [
      "section",
      "dense"
    ],
    "e19": [
      "section",
      "dense"
    ],
    "e21": [
      "section",
      "dense"
    ],
    "e24": [
      "section",
      "dense"
    ],
    "e27": [
      "section",
      "dense"
    ],
    "e29": [
      "section",
      "dense"
    ],
    "e37": [
      "section",
      "dense"
    ],
    "e43": [
      "section",
      "dense"
    ],
    "e28": [
      "section",
      "dense"
    ]
  },
  "28": {
    "e21": [
      "component",
      "dense"
    ],
    "e24": [
      "component",
      "dense"
    ],
    "e26": [
      "component",
      "dense"
    ],
    "e23": [
      "component",
      "dense"
    ],
    "e8": [
      "component",
      "dense"
    ],
    "e28": [
      "component",
      "dense"
    ],
    "e30": [
      "component",
      "dense"
    ],
    "e10": [
      "component",
      "dense"
    ],
    "e9": [
      "component",
      "dense"
    ],
    "e15": [
      "component",
      "dense"
    ],
    "e51": [
      "component",
      "dense"
    ],
    "e20": [
      "component",
      "dense"
    ],
    "e52": [
      "component",
      "dense"
    ],
    "e53": [
      "component",
      "dense"
    ]
  }
}, iconCards:{
  "71": {
    "padding": 0.12,
    "gap": 0.12,
    "paragraphGap": 0.07,
    "iconSize": 0.432,
    "cards": [
      {
        "body": "e21",
        "icon": [
          "e34",
          "e41"
        ]
      },
      {
        "body": "e24",
        "icon": [
          "e35",
          "e42"
        ]
      },
      {
        "body": "e22",
        "icon": [
          "e36",
          "e43"
        ]
      },
      {
        "body": "e23",
        "icon": [
          "e37",
          "e44"
        ]
      }
    ]
  },
  "64": {
    "padding": 0.12,
    "gap": 0.06,
    "paragraphGap": 0.04,
    "iconSize": 0.41,
    "cards": [
      {
        "body": "e115",
        "headingParagraphs": 2,
        "icon": [
          "e325"
        ]
      },
      {
        "body": "e336",
        "headingParagraphs": 2,
        "icon": [
          "e337",
          "e344"
        ]
      }
    ]
  }
}, cards:{
  "51": {
    "group": "e18",
    "bannerGroup": "e19",
    "banner": "e10",
    "bannerTop": 1.62,
    "bannerHeight": 0.46,
    "padding": 0.12,
    "compactPadding": 0.06,
    "internalGap": 0.04,
    "badgeSize": 0.26,
    "badgeGap": 0.12,
    "gap": 0.12,
    "columns": 4,
    "cards": [
      {
        "group": "e6",
        "title": "e57",
        "badge": "e59",
        "body": "e92",
        "owners": [
          "e61",
          "e91"
        ]
      },
      {
        "group": "e15",
        "title": "e63",
        "badge": "e80",
        "body": "e101",
        "owners": [
          "e99",
          "e100"
        ]
      },
      {
        "group": "e16",
        "title": "e64",
        "badge": "e81",
        "body": "e105",
        "owners": [
          "e103",
          "e104"
        ]
      },
      {
        "group": "e17",
        "title": "e65",
        "badge": "e82",
        "body": "e109",
        "owners": [
          "e107",
          "e108"
        ]
      },
      {
        "group": "e14",
        "title": "e76",
        "badge": "e88",
        "body": "e125",
        "owners": [
          "e126",
          "e123",
          "e124"
        ]
      },
      {
        "group": "e11",
        "title": "e77",
        "badge": "e85",
        "body": "e113",
        "owners": [
          "e111",
          "e112"
        ]
      },
      {
        "group": "e7",
        "title": "e79",
        "badge": "e87",
        "body": "e121",
        "owners": [
          "e119",
          "e120"
        ]
      },
      {
        "group": "e8",
        "title": "e78",
        "badge": "e86",
        "body": "e117",
        "owners": [
          "e115",
          "e116"
        ]
      }
    ]
  }
}, panels:{
    "52": {
        "padding": 0.12,
        "gap": 0.12,
        "paragraphGap": 0.04,
        "markerLane": 0.12,
        "markerGap": 0.08,
        "markerSize": 0.09,
        "panels": [
            {
                "background": "e30",
                "header": "e228",
                "body": "e13",
                "icon": [
                    "e235",
                    "e234"
                ],
                "markers": [
                    "e252",
                    "e9",
                    "e250",
                    "e39"
                ]
            },
            {
                "background": "e50",
                "header": "e227",
                "body": "e51",
                "icon": [
                    "e239",
                    "e229"
                ],
                "markers": [
                    "e65",
                    "e34",
                    "e26",
                    "e80"
                ]
            },
            {
                "background": "e60",
                "header": "e138",
                "body": "e64",
                "icon": [
                    "e242",
                    "e230"
                ],
                "markers": [
                    "e68",
                    "e36",
                    "e31"
                ]
            },
            {
                "background": "e62",
                "header": "e139",
                "body": "e71",
                "icon": [
                    "e245",
                    "e232"
                ],
                "markers": [
                    "e19",
                    "e16",
                    "e253"
                ]
            },
            {
                "background": "e63",
                "header": "e137",
                "body": "e75",
                "icon": [
                    "e248",
                    "e231"
                ],
                "markers": [
                    "e38",
                    "e236",
                    "e59"
                ]
            }
        ],
        "legend": {
            "group": "e37",
            "items": [
                [
                    "e28",
                    "e29"
                ],
                [
                    "e224",
                    "e226"
                ]
            ]
        },
        "labels": {
            "header": "e22",
            "body": "e23"
        }
    }
}, footer:{top:6.8,bottom:7.32,gap:0.14,auxiliary:{23:['custom.cadence'],34:['custom.legend'],65:['custom.appendix']}},
    tableIcons:{'58.custom.tactics':{column:1,textColumn:2,prefix:'tactic-icon',size:0.32,gap:0.12}},
    tableHeaders:{'38.e9':{minHeight:0.72,anchor:'b'}},
    stacks:{45:[{ids:['e8','e9','e10','e11','e270'],right:8.7}]} },
  // Canonical sizes distilled from the reference hierarchy, shared by all slides.
  hierarchy: { enabled: true, sizes: { coverTitle:60, sectionCoverTitle:66, coverNumber:28, title:22, subtitle:14, section:11,
    component:12, chartTitle:10, tableHeader:10, kicker:10, statement:16, display:18 }, roles: {} },
};

/**
 * Papéis de matrizes e diagramas do repositório, identificados por ID original.
 * Permanecem configuráveis em quality.roles. Não são texto corrido: representam
 * células de matrizes, organogramas, anotações de cronograma e legendas de figuras.
 */
const diagramRoles = {
  21:['e34','e35','e37','e38','e48'],
  16: ['e22'], 24:['e21','e28','e19','e24','e29','e43'],
  35:['e62','e147'], 41:['e306','e307'], 43:['e5','e234','e236','e237'],
  47:['e23','e24','e25','e26'], 67:['e7'], 71:['e9','e20'], 22: ['e37','e9','e11','e12'],
  27: ['e53','e12'], 37: ['e366'],
  51: ['e10','e57','e63','e64','e65','e76','e77','e78','e79','e92','e101','e105','e109','e113','e117','e121','e125'], 52: ['e71','e13','e51','e64','e75','e137','e138','e139','e227','e228','e29','e226','e22','e23'],
  61: ['e1129','e1093','e1094'], 62: ['e66','e67','e72','e75'],
};

/** Obtém texto de um ID estável do catálogo, sem reescrever conteúdo ou valores. */
function sourceText(catalog, number, id) {
  return catalog.slides[number-1].elements.find(e => e.id === id)?.text.trim() || '';
}

/** Obtém a matriz de uma tabela original; a cópia permite alterar só sua composição. */
function sourceTable(catalog, number, id) {
  return structuredClone(catalog.slides[number-1].elements.find(e => e.id === id).cells);
}

/**
 * Cria primitivas declarativas para um slide. out recebe as declarações; q contém
 * tokens resolvidos. Cada objeto tem ID e pode ser configurado antes do scaffold.
 */
function toolsFor(out, q) {
  return {
    /** Texto com tamanho explícito e sem shrink silencioso do PowerPoint. */
    text(id, text, box, style = {}) {
      out.push({ id, kind: 'text', text, box, style: { fontFace: q.font,
        fontSize: q.type.body.size, margin: 0, breakLine: false, valign: 'top',
        color: '000000', paraSpaceAfterPt: 0, ...style } });
    },
    /** Forma editável para faixas e divisórias; não depende de fonte de ícones. */
    shape(id, box, color, line = color) {
      out.push({ id, kind: 'shape', type: 'rect', box,
        style: { fill: { color }, line: { color: line, width: 0.6 } } });
    },
    /**
     * Tabela nativa com linhas dimensionadas pelo conteúdo de TODAS as colunas.
     * widths são polegadas, somando box.w. Não reduz fonte abaixo de dense.min.
     * Uma caixa insuficiente interrompe a geração em vez de recortar os dados.
     */
    table(id, matrix, box, widths, options = {}) {
      let fontSize = options.fontSize || q.type.dense.size;
      const padding = q.spacing.tablePadding;
      /** Mede toda a tabela com uma fonte uniforme, incluindo padding e cabeçalho. */
      const measure = size => matrix.map((row, ri) => Math.max(0.23,
        ...row.map((value, ci) => textHeight(value, widths[ci]-2*padding/72, size,
          { bold: ri === 0, leading: q.spacing.leading, safety: 1.02 })+2*padding/72)));
      let heights = measure(fontSize);
      while (q.fontFit.enabled && fontSize > q.type.dense.min && heights.reduce((a,b) => a+b,0) > box.h+0.01) {
        fontSize = Math.max(q.type.dense.min, Math.round((fontSize-q.fontFit.step)*100)/100);
        heights = measure(fontSize);
      }
      const required = heights.reduce((a, b) => a+b, 0);
      if (required > box.h+0.01) throw new Error(`Tabela ${id}: precisa ${required.toFixed(2)}in, disponível ${box.h.toFixed(2)}in a ${fontSize}pt`);
      const extra = (box.h-required)/heights.length;
      const rows = matrix.map((row, ri) => row.map(value => ({ text: value,
        options: { bold: ri === 0, color: ri === 0 ? 'FFFFFF' : '000000',
          fill: ri === 0 ? 'EC111A' : ri % 2 ? 'FFFFFF' : 'F5EFE8' } })));
      out.push({ id, kind: 'table', rows, box, style: { fontFace: q.font, fontSize,
        margin: padding, colW: widths, rowH: heights.map(h => h+extra),
        border: { type: 'solid', pt: 0.4, color: 'D8D6CA' },
        valign: 'middle', autoPage: false, ...options, fontSize } });
    },
    /**
     * Gráfico Office editável, com categorias, valores e workbook incorporado.
     * series contém os caches numéricos originais; style controla eixos/legendas.
     */
    chart(id, series, box, style = {}) {
      out.push({ id, kind: 'chart', type: 'bar', series, box,
        style: { catAxisLabelFontFace: q.font, valAxisLabelFontFace: q.font,
          catAxisLabelFontSize: q.type.dense.size, valAxisLabelFontSize: q.type.dense.size,
          dataLabelFormatCode: '#,##0', dataLabelPosition: 'outEnd',
          dataLabelColor: '000000', dataLabelBkgrdColor: 'FFFFFF',
          dataLabelFormatCodeSourceLinked: false, dataLabelFontFace: q.font,
          dataLabelFontSize: q.type.dense.size, legendFontFace: q.font,
          legendFontSize: q.type.dense.size, showTitle: false, showLegend: false,
          showValue: true, showCatName: false, showBorder: false,
          catAxisLineShow: false, valAxisLineShow: false, valAxisHidden: true,
          catAxisLabelPos: 'low', catAxisMajorTickMark: 'none',
          valGridLine: { style: 'none' }, chartColors: ['D8D6CA','EC111A'],
          showShadow: false, showMarker: false, gapSizePct: 90,
          ...style } });
    },
  };
}

/** Agenda completa em tabela, com largura suficiente para Length e última linha. */
function agenda(catalog, out, q) {
  const t = toolsFor(out, q), rows = sourceTable(catalog, 10, 'e8');
  t.table('agenda', rows, { x: 0.56, y: 1.20, w: 12.21, h: 6.10 },
    [0.98, 0.58, 3.94, 0.94, 1.81, 3.96]);
}

/**
 * Timeline densa em tabela + barras editáveis. A posição horizontal de cada
 * barra é a transformação linear da geometria original, sem inventar datas.
 * As alturas das linhas seguem a medição de entregáveis, não o desenho antigo.
 */
function timeline(catalog, out, q) {
  const t = toolsFor(out, q), data = sourceTable(catalog, 23, 'e57');
  const rows = [['Workstream', 'Deliverables', 'Jan     Feb     Mar     Apr     May     Jun', 'Outputs']];
  let workstream = '';
  for (const row of data.slice(1)) {
    if (row[0].trim()) workstream = row[0].trim();
    rows.push([row[0].trim() ? workstream : '', row[2]+' '+row[3], '', row[28]]);
  }
  t.table('timeline', rows, { x: 0.56, y: 1.7, w: 12.21, h: 5.08 }, [1.6,4.1,3.16,3.35]);
  const table = out.find(e => e.id === 'timeline');
  const ids = ['e17','e47','e26','e31','e27','e28','e29','e30','e32','e14','e33','e35'];
  let y = 1.7+table.style.rowH[0];
  for (let i = 0; i < ids.length; i++) {
    const original = catalog.slides[22].elements.find(e => e.id === ids[i]).box;
    const x = 6.26+(original.x-6.0)/4.9*3.16;
    const w = original.w/4.9*3.16;
    t.shape(`timeline-bar-${i}`, { x, y: y+table.style.rowH[i+1]/2-0.065, w, h: 0.13 }, 'A6A6A6');
    y += table.style.rowH[i+1];
  }
  // Original future-extension outlines retain their exact relative time positions.
  for (const id of ['e22','e11','e13','e3','e24']) {
    const original = catalog.slides[22].elements.find(e => e.id === id).box;
    const row = Math.max(0, Math.min(11, Math.round((original.y-2.43)/0.32)));
    const y0 = 1.7+table.style.rowH.slice(0,row+1).reduce((a,b) => a+b,0)+table.style.rowH[row+1]/2-0.065;
    t.shape(`extension-${id}`, { x: 6.26+(original.x-6.0)/4.9*3.16, y: y0,
      w: original.w/4.9*3.16, h: 0.13 }, 'FFFFFF', 'BCB8A4');
    out.at(-1).style.fill.transparency = 100;
    out.at(-1).style.line.dashType = 'dash';
  }
  t.text('cadence', sourceText(catalog,23,'e46'), { x: 0.56, y: 6.93, w: 12.21, h: 0.25 },
    { fontSize: 10, color: 'EC111A', bold: true });
}

/** Governança nativa em matriz: cada nível e seu mandato ocupam a mesma linha. */
function governance(catalog, out, q) {
  const t = toolsFor(out, q);
  /** Texto original de um elemento da matriz de governança. */
  const s = id => sourceText(catalog, 29, id);
  t.table('governance', [
    ['Governance', 'Team / participants', 'Team / participants', 'Mandate and cadence'],
    [s('e52'), s('e53'), s('e54'), s('e49')],
    [s('e30'), s('e41'), s('e42'), s('e47')],
    [s('e55'), s('e56'), s('e57'), s('e60')],
    [s('e29'), s('e59'), s('e50')+'\n\n'+s('e58'), s('e48')],
  ], { x: 0.56, y: 1.65, w: 12.21, h: 5.5 }, [1.36, 3.65, 3.65, 3.55]);
}

/**
 * Recria os quatro gráficos a partir dos valores originais; nenhuma barra é SVG.
 * Os rótulos usam anos explícitos. A série de clientes converte pessoas em milhões.
 */
function impressions(catalog, out, q, charts) {
  const t = toolsFor(out, q), s = id => sourceText(catalog, 31, id);
  const summaries = ['Operational efficiency delivered through disciplined branch reduction and cost management…',
    '…but overall growth remains flat and below market limiting top-line growth potential'];
  for (let j = 0; j < 2; j++) {
    const x = 0.56+j*6.18;
    t.text(`section-${j}`, j ? 'STAGNANT GROWTH' : 'OPERATIONAL EFFICIENCY',
      { x, y: 1.65, w: 6.02, h: 0.25 }, { bold: true });
    t.text(`summary-${j}`, summaries[j], { x, y: 1.99, w: 6.02, h: 0.48 });
  }
  const titles = ['Branch Reductions','Retail Expenses in CAD $MM','Retail Clients in MM','Retail Revenue in CAD $MM'];
  const deltas = ['−120 branches','1.4% CAGR · SBM 4% / inflation 14% over 3Y','−0.1% total · SME −3.3% / PB +0.3%','5.4% CAGR · Est. 3Y market growth +9.4%'];
  for (let i = 0; i < 4; i++) {
    const x = 0.56+i*3.09;
    t.shape(`panel-${i}`, { x, y: 2.59, w: 2.94, h: 2.4 }, 'F5EFE8');
    t.text(`chart-title-${i}`, titles[i], { x: x+0.09, y: 2.69, w: 2.76, h: 0.4 }, { fontSize: q.type.body.size, bold: true });
    const original = charts[`ppt/charts/chart${i+1}.xml`][0].series;
    const series = original.map((ser, index) => ({ name: i === 2 ? ['PB','SME'][index] : titles[i],
      labels: i === 0 ? ['2021','2025'] : ['2022','2025'],
      values: ser.values.map(value => i === 2 ? value/1e6 : value) }));
    t.chart(`chart-${i}`, series, { x: x+0.1, y: 3.12, w: 2.74, h: 1.38 },
      { barGrouping: i === 2 ? 'stacked' : 'clustered',
        chartColors: i === 2 ? ['D8D6CA','EC111A'] : ['EC111A'],
        showLegend: i === 2, legendPos: 'b', showValue: i !== 2,
        dataLabelFormatCode: i === 2 ? '0.00' : '#,##0',
        catAxisHidden: false });
    t.text(`delta-${i}`, deltas[i], { x: x+0.09, y: 4.57, w: 2.76, h: 0.38 },
      { fontSize: 10, bold: true, align: 'center' });
  }
  const left = s('e237').split(/\n/).filter(Boolean).slice(2).join('\n');
  const right = s('e2593').split(/\n/).filter(Boolean).slice(2).join('\n');
  t.text('notes-left', left, { x: 0.56, y: 5.13, w: 6.02, h: 0.8 });
  t.text('notes-right', right, { x: 6.74, y: 5.13, w: 6.03, h: 0.8 });
  t.shape('conclusion-band', { x: 0.56, y: 6.16, w: 12.21, h: 0.5 }, 'EC111A');
  t.text('conclusion', s('e2689'), { x: 0.68, y: 6.20, w: 11.97, h: 0.42 },
    { fontSize: q.type.body.size, bold: true, color: 'FFFFFF' });
}

/** Comparação em tabela editável, sem margens internas negativas nem texto invertido. */
function comparison(catalog, out, q) {
  const t = toolsFor(out, q), s = id => sourceText(catalog, 34, id);
  const rows = [
    ['', 'ADVISOR-LED', 'HYBRID PLANNING', 'HYBRID INVESTING', 'DIRECT INVESTING'],
    ['Description', s('e98'), s('e97'), s('e99'), s('e100')],
    ['Product focus', s('e104'), s('e176'), s('e106'), s('e107')],
    ['Channel positioning', 'Advisory focus\nHigh cost', 'Limited advisory\nHigh–medium cost', 'Limited advisory\nLow–medium cost', 'No advisory\nLow cost'],
    ['Scotiabank', s('e151'), s('e160'), s('e226'), s('e165')],
    ['RBC', s('e1133'), s('e1135'), s('e1134'), s('e1136')],
    ['BMO', s('e150'), s('e159'), s('e155'), s('e164')],
    ['TD Bank', s('e149'), s('e158'), s('e154'), s('e163')],
    ['CIBC', s('e152'), s('e161'), s('e156'), s('e166')],
    ['Wealthsimple', s('e192'), s('e230'), s('e207'), s('e194')],
    ['Questrade', s('e241'), s('e231'), s('e208'), s('e205')],
  ];
  t.table('comparison', rows, { x: 0.56, y: 1.9, w: 12.21, h: 4.88 }, [1.49, 2.68, 2.68, 2.68, 2.68]);
  const states = [[0,1,2,1],[0,0,0,1],[0,0,0,1],[0,1,2,0],[0,1,2,1],[1,2,0,1],[2,2,0,0]];
  // Status remains editable text in each cell; color and meaning are both explicit.
  const table = out.find(e => e.id === 'comparison');
  for (let r = 0; r < states.length; r++) for (let c = 0; c < 4; c++) {
    const cell = table.rows[r+4][c+1];
    cell.options.color = ['00594F','9C6900','EC111A'][states[r][c]];
    cell.text += '\n'+['Strong','Developing','Weak'][states[r][c]];
  }
  t.text('legend', 'Strength of capabilities: Strong / Developing / Weak',
    { x: 0.56, y: 6.94, w: 11.7, h: 0.2 }, { fontSize: 10 });
}

/** Mix de balanço: duas séries de barras empilhadas nativas e KPIs sem sobreposições. */
function balance(catalog, out, q, charts) {
  const t = toolsFor(out, q);
  const banks = ['Scotia','BBVA','HSBC','Santander','Banorte','System'];
  for (let side = 0; side < 2; side++) {
    const x = 0.56+side*6.18;
    t.text(`heading-${side}`, side ? 'DEPOSITS MIX, LOCAL GAAP BENCHMARK' : 'LOANS MIX, LOCAL GAAP BENCHMARK',
      { x, y: 1.85, w: 6.03, h: 0.27 }, { bold: true });
    const names = side ? ['Term','Savings','Demand'] : ['GBM + Comm','Mortgage','Auto','Unsecured'];
    const colors = side ? ['EBDFD1','BCB8A4','EC111A'] : ['EBDFD1','BCB8A4','B10D13','EC111A'];
    const data = q.elements[`40.mix-${side}`]?.series || charts[`ppt/charts/chart${9+side}.xml`][0].series.map((ser, i) => ({
      name: names[i], labels: banks, values: ser.values,
    }));
    t.chart(`mix-${side}`, data, { x, y: 2.22, w: 6.03, h: 2.67 },
      { barGrouping: 'stacked', chartColors: colors, showLegend: true, legendPos: 't',
        showValue: true, dataLabelPosition: 'ctr', dataLabelFormatCode: '0"%"',
        valAxisMaxVal: 100, catAxisHidden: false, dataLabelColor: '000000' });
    if (side === 0) {
      const auto = data[2].values.map(value => Math.round(value)).join(', ');
      t.text('small-segments', `Auto (%), Scotia to System: ${auto}. Scotia unsecured: ${Math.round(data[3].values[0])}%.`,
        { x, y: 4.9, w: 6.03, h: 0.28 }, { fontSize: q.type.dense.size });
    }
    const cells = sourceTable(catalog, 40, side ? 'e460' : 'e429');
    const rows = [['Metric', ...banks],
      [side ? 'Deposits CoF\nY/Y var.' : 'Loans yield\nY/Y var.', ...cells[1]],
      [side ? 'LDR' : 'PCL ratio\nY/Y var.', ...cells[3]]];
    t.table(`kpi-${side}`, rows, { x, y: 5.25, w: 6.03, h: 1.24 }, [1.05,0.83,0.83,0.83,0.83,0.83,0.83]);
  }
}

/**
 * Desenha um ícone Office editável em uma caixa quadrada. kind seleciona o
 * símbolo sem usar fontes de ícones. Coordenadas locais 0–1 escalam com box;
 * prefix identifica todas as peças para ancoragem posterior à linha da tabela.
 */
function tacticIcon(out, prefix, kind, box, q) {
  const t = toolsFor(out,q);
  let index = 0;
  /** Adiciona uma peça vetorial proporcional à caixa, com contorno branco. */
  const piece = (type,x,y,w,h,solid=false,rotation=0) => out.push({
    id:`${prefix}-${index++}`,kind:'shape',type,
    box:{x:box.x+x*box.w,y:box.y+y*box.h,w:Math.max(w,0.001)*box.w,h:Math.max(h,0.001)*box.h},
    style:{fill:{color:'FFFFFF',transparency:solid?0:100},line:{color:'FFFFFF',width:0.8},rotate:rotation},
  });
  t.shape(`${prefix}-bg`,box,'EC111A');
  if (kind==='youth' || kind==='team') {
    for (const center of kind==='team' ? [0.24,0.5,0.76] : [0.35,0.65]) {
      piece('ellipse',center-0.08,0.2,0.16,0.16);
      piece('roundRect',center-0.12,0.42,0.24,0.35);
    }
  } else if (kind==='winter') {
    piece('line',0.2,0.5,0.6,0);
    piece('line',0.5,0.2,0,0.6);
    piece('line',0.28,0.28,0.44,0.44);
    piece('line',0.28,0.28,0.44,0.44,false,90);
  } else if (kind==='inbound' || kind==='outbound') {
    piece(kind==='inbound'?'downArrow':'upArrow',0.33,0.16,0.34,0.56,true);
    piece('line',0.2,0.82,0.6,0);
  } else if (kind==='pricing') {
    piece('ellipse',0.2,0.2,0.15,0.15);
    piece('ellipse',0.65,0.65,0.15,0.15);
    piece('line',0.27,0.23,0.46,0.54,false,90);
  } else if (kind==='wealth') {
    for (let i=0;i<3;i++) piece('rect',0.2+i*0.23,0.65-i*0.2,0.13,0.2+i*0.2,true);
  } else {
    piece('heart',0.18,0.22,0.64,0.56);
  }
}

/**
 * Táticas em tabela com coluna exclusiva de ícones antes do texto. size/gap
 * vêm de flow.tableIcons; o adaptador ancora as peças nas alturas finais das
 * linhas, inclusive quando uma descrição cresce ou a fonte é reconfigurada.
 */
function tactics(catalog, out, q) {
  const t = toolsFor(out, q), original = sourceTable(catalog, 58, 'e14');
  const rows = original.map((row, i) => i ? [i <= 4 ? 'ACTIVE' : 'PLANNED\n(F26)', '', ...row] : ['STATUS','', ...row]);
  t.table('tactics', rows, { x:0.56,y:1.65,w:12.21,h:5.01 }, [0.75,0.5,2.2,4.32,4.44]);
  const table = out.find(e=>e.id==='tactics');
  const settings = q.flow.tableIcons['58.custom.tactics'];
  const kinds = settings.kinds || ['youth','winter','team','inbound','outbound','pricing','wealth','engagement'];
  if (kinds.length!==rows.length-1) throw new Error('Tactics: configure um ícone por linha');
  let y = table.box.y+table.style.rowH[0];
  for (let row=0;row<kinds.length;row++) {
    tacticIcon(out,`${settings.prefix}-${row+1}`,kinds[row],{
      x:table.box.x+0.75+0.5+q.spacing.tablePadding/72-settings.gap-settings.size,
      y:y+(table.style.rowH[row+1]-settings.size)/2,w:settings.size,h:settings.size,
    },q);
    y += table.style.rowH[row+1];
  }
}

/** Roadmap em matriz de iniciativas: cada célula tem título e objetivo completos. */
function roadmap(catalog, out, q) {
  const t = toolsFor(out, q), s = id => sourceText(catalog, 65, id);
  t.text('overview-heading', 'OVERVIEW', { x: 0.56, y: 1.85, w: 2.2, h: 0.25 }, { bold: true });
  t.text('overview', s('e20'), { x: 0.56, y: 2.25, w: 2.2, h: 4.2 });
  t.text('long-term', s('e28'), { x: 2.94, y: 1.85, w: 9.83, h: 0.28 }, { bold: true });
  const groups = [ ['RETAIL', ['e13','e110','e27','e14','e21']], ['WEALTH',['e64','e24','e75']],
    ['TANGERINE',['e76','e97','e98','e99']] ];
  for (let r = 0; r < groups.length; r++) {
    const [label, ids] = groups[r], y = 2.29+r*1.5, color = r === 2 ? 'EE8447' : 'EC111A';
    t.shape(`label-bg-${r}`, { x: 2.94, y, w: 0.43, h: 1.36 }, color);
    // One horizontal line rotated as a whole: no stacked characters or word wrap.
    t.text(`label-${r}`, label, { x: 2.46, y: y+0.52, w: 1.39, h: 0.31 },
      { fontSize: q.type.body.size, color: 'FFFFFF', bold: true, rotate: 270, wrap: false, align: 'center' });
    const w = (9.25-(ids.length-1)*q.spacing.gap)/ids.length;
    for (let i = 0; i < ids.length; i++) {
      const x = 3.52+i*(w+q.spacing.gap), [title,...body] = s(ids[i]).split('\n');
      t.shape(`card-${r}-${i}`, { x, y, w, h: 1.36 }, 'FFFFFF', color);
      t.text(`card-title-${r}-${i}`, title, { x: x+0.08, y: y+0.1, w: w-0.16, h: 0.5 },
        { fontSize: q.type.body.size, bold: true });
      t.text(`card-body-${r}-${i}`, body.join('\n'), { x: x+0.08, y: y+0.65, w: w-0.16, h: 0.61 },
        { fontSize: 10 });
    }
  }
  t.text('appendix', s('e78'), { x: 2.94, y: 6.94, w: 9.1, h: 0.2 },
    { fontSize: 10, bold: true, color: 'EC111A' });
}

/**
 * Resolve tokens e configura substituições apenas dos layouts solicitados.
 * catalog é o catálogo imutável. patch é clonado. Todas as remoções referem-se
 * a IDs originais de primeiro nível, para não remover filhos duas vezes.
 * As funções da biblioteca geram tabelas e gráficos; a importação OPC conserva
 * workbook e relações. O perfil Python normaliza a tipografia do pacote final.
 */
export function prepareQuality(patch, catalog) {
  const config = structuredClone(patch), q = merge(qualityDefaults, patch.quality);
  if (!Number.isFinite(q.fontFit.step) || q.fontFit.step < 0.01)
    throw new Error('fontFit.step deve ser pelo menos 0.01 pt');
  for (const [number, ids] of Object.entries(diagramRoles))
    for (const id of ids) q.roles[`${number}.${id}`] ||= 'dense';
  for (const [role, limits] of Object.entries(q.type))
    if (!(limits.min > 0 && limits.max >= limits.min && limits.size >= limits.min && limits.size <= limits.max)) throw new Error(`Escala inválida: ${role}`);
  for (const [role,size] of Object.entries(q.hierarchy.sizes))
    if (!Number.isFinite(size) || size <= 0) throw new Error(`Token tipográfico inválido: ${role}`);
  for (const role of Object.values(q.hierarchy.roles))
    if (!(role in q.hierarchy.sizes)) throw new Error(`Nível tipográfico desconhecido: ${role}`);
  if (q.spacing.tablePadding < 0 || q.spacing.gap < 0) throw new Error('Espaçamentos não podem ser negativos');
  // Capture reference sizes before any transformation; explicit element tokens win.
  for (const slide of catalog.slides) for (const item of slide.elements)
    if (item.typography?.size) q.referenceTypography.elements[`${slide.number || catalog.slides.indexOf(slide)+1}.${item.id}`] ||= item.typography;
  // Capas usam placeholders body na referência: não podem herdar corpo 12 pt.
  // A classificação usa tamanho/posição do catálogo, com tokens globais e
  // overrides explícitos preservados. A geometria cresce no adaptador nativo.
  for (const slide of catalog.slides) {
    const cover = slide.elements.find(item=>item.typography?.size>=48 && item.box?.y>2);
    if (!cover) continue;
    const key = `${slide.number}.${cover.id}`;
    q.hierarchy.roles[key] ||= cover.typography.size>62 ? 'sectionCoverTitle' : 'coverTitle';
    for (const item of slide.elements) {
      if (item.id===cover.id || !item.text?.trim()) continue;
      if (/^\d+$/.test(item.text.trim()) && item.typography?.size>=24)
        q.hierarchy.roles[`${slide.number}.${item.id}`] ||= 'coverNumber';
      else if (item.typography?.size>=16)
        q.hierarchy.roles[`${slide.number}.${item.id}`] ||= 'statement';
      else if (item.typography?.size>=14)
        q.hierarchy.roles[`${slide.number}.${item.id}`] ||= 'subtitle';
    }
  }
  const charts = catalog.chartSources || JSON.parse(fs.readFileSync(path.join(root, 'data/chart-source.json')));
  config.quality = q;
  config.theme = merge({ fonts: { body: q.font, heading: q.font } }, config.theme || {});
  config.slides ||= {}; config.additions ||= {};
  // Give the left timeline annotation the full width of its source column.
  for (const [key, box] of Object.entries({
    ...Object.fromEntries(['e34','e35','e37','e38','e48'].map(id=>[`21.${id}`,{...catalog.slides[20].elements.find(e=>e.id===id).box,h:1.95}])),
    '16.e22': { x:0.56, y:3.07, w:3.45, h:2.94 },
    '27.e53': { x:0.73, y:4.15, w:2.11, h:2.5 },
    '22.e6': { x:9.31, y:5.16, w:0.17, h:0.17 },
    '22.e7': { x:9.31, y:5.95, w:0.17, h:0.17 },
    '22.e11': { x:9.30, y:5.14, w:3.53, h:0.73 },
    '22.e12': { x:9.30, y:5.93, w:3.53, h:0.73 },
    '22.e6': { x:9.31, y:5.40, w:0.18, h:0.18 },
    '22.e7': { x:9.31, y:6.16, w:0.18, h:0.18 },
    '25.e193': { x:7.23, y:6.58, w:1.3, h:0.34 },
    '39.e179': { x:1.82, y:2.5968, w:0.49, h:0.19 },
    '44.e500': { x:3.9874, y:5.56, w:0.54, h:0.34 },
    '44.e508': { x:8.1327, y:5.56, w:0.54, h:0.34 },
    '44.e525': { x:12.278, y:5.56, w:0.54, h:0.34 },
    '45.e78': { x:0.56, y:6.98, w:11.61, h:0.38 },
    '47.e408': { x:11.07, y:4.7726, w:0.48, h:0.17 },
    '45.e154': { x:11.69, y:1.61, w:1.08, h:0.42 },
    '70.e2': { x:9.45, y:2.30, w:3.4, h:4.45 },
    '55.e2': { x:0.56, y:0.724, w:12.21, h:1.07 },
  })) {
    const [number,id] = key.split('.');
    if (!config.selection || config.selection.includes(Number(number))) {
      config.slides[number] ||= {};
      config.slides[number].elements ||= {};
      config.slides[number].elements[id] = { box, ...config.slides[number].elements[id] };
    }
  }
  const builders = { 10: agenda, 23: timeline, 29: governance, 31: impressions, 34: comparison,
    40: balance, 58: tactics, 65: roadmap };
  for (const number of q.repairSlides) {
    if (config.selection && !config.selection.includes(number)) continue;
    const descriptor = catalog.slides[number-1];
    config.slides[number] ||= {};
    const elements = config.slides[number].elements ||= {};
    for (const item of descriptor.elements) {
      if (item.parentId || !item.box) continue;
      const isHeader = item.kind === 'shape' && item.box.y < 1.3 && item.text;
      const isNote = /^Source:/i.test(item.text) || item.box.y >= 7.1;
      if (!isHeader && !isNote) elements[item.id] = { visible: false };
    }
    const out = [];
    if (!builders[number]) throw new Error(`Não existe reparo específico para ${number}`);
    builders[number](catalog, out, q, charts);
    // Rebuilt structural text inherits its source size, rather than a body token.
    const headingSources = {
      31: { 'section-0':'e237', 'section-1':'e2593', 'chart-title-0':'e246', 'chart-title-1':'e247', 'chart-title-2':'e2595', 'chart-title-3':'e2596' },
      40: { 'heading-0':'e6', 'heading-1':'e11' },
      65: { 'overview-heading':'e16', 'long-term':'e28', 'label-0':'e84', 'label-1':'e80', 'label-2':'e88',
        ...Object.fromEntries([['e13','e110','e27','e14','e21'],['e64','e24','e75'],['e76','e97','e98','e99']]
          .flatMap((ids,r)=>ids.map((id,i)=>[`card-title-${r}-${i}`,id]))) },
    };
    for (const item of out) {
      const sourceId = headingSources[number]?.[item.id];
      const reference = q.referenceTypography.elements[`${number}.${sourceId}`];
      if ((q.referenceTypography.enabled || q.hierarchy.enabled) && reference?.size && item.kind === 'text') {
        const inferred = item.id.startsWith('chart-title-') ? 'chartTitle'
          : item.id.startsWith('card-title-') || item.id.startsWith('label-') ? 'component' : 'section';
        const level = q.hierarchy.roles[`${number}.custom.${item.id}`] || inferred;
        const size = q.hierarchy.enabled ? q.hierarchy.sizes[level]
          : q.elements[`${number}.${item.id}`]?.style?.fontSize || reference.size;
        q.hierarchy.roles[`${number}.custom.${item.id}`] ||= level;
        item.style.fontSize = size;
        q.referenceTypography.elements[`${number}.custom.${item.id}`] = { ...reference, size, locked: true };
      }
    }
    const tableSources = { 10:['agenda','e8'], 23:['timeline','e57'], 34:['comparison',null], 40:['kpi-0','e429'], 58:['tactics','e14'] };
    const tableSource = tableSources[number];
    if ((q.referenceTypography.enabled || q.hierarchy.enabled) && tableSource?.[1]) {
      const source = descriptor.elements.find(e=>e.id===tableSource[1]);
      const headerSize = q.hierarchy.enabled ? q.hierarchy.sizes.tableHeader : Math.max(...(source?.headerFontSizes || [q.type.dense.size]));
      for (const item of out.filter(e=>e.kind==='table' && (e.id===tableSource[0] || number===40))) {
        for (const cell of item.rows[0]) cell.options.fontSize = headerSize;
        q.referenceTypography.elements[`${number}.custom.${item.id}`] = { headerSize };
      }
    }
    if (q.hierarchy.enabled) for (const item of out.filter(e=>e.kind==='table')) {
      for (const cell of item.rows[0]) cell.options.fontSize = q.hierarchy.sizes.tableHeader;
      q.referenceTypography.elements[`${number}.custom.${item.id}`] = { headerSize:q.hierarchy.sizes.tableHeader };
    }
    for (const item of out) {
      if (item.kind === 'shape') continue;
      const size = item.style.fontSize || q.type.dense.size;
      const role = item.kind === 'text' && size >= q.type.body.min ? 'body' : 'dense';
      q.roles[`${number}.custom.${item.id}`] ||= role;
    }
    config.additions[number] = [...out.map(item => {
      const effective = merge(item, q.elements[`${number}.${item.id}`] || {});
      if (effective.kind !== 'shape') {
        const role = q.roles[`${number}.custom.${effective.id}`];
        const size = effective.style.fontSize || q.type.dense.size;
        if (!q.referenceTypography.elements[`${number}.custom.${effective.id}`]?.locked && (size < q.type[role].min || size > q.type[role].max))
          throw new Error(`${number}.${effective.id}: fonte ${size}pt fora dos limites de ${role}`);
      }
      if (q.hierarchy.enabled && q.referenceTypography.elements[`${number}.custom.${item.id}`]?.locked)
        effective.style.fontSize = q.hierarchy.sizes[q.hierarchy.roles[`${number}.custom.${item.id}`]];
      return effective;
    }), ...(config.additions[number] || [])];
  }
  return config;
}
