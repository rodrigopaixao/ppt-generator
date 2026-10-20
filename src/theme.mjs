/**
 * Tokens e configuração dos sete templates adaptativos. O modo fiel preserva
 * os temas do arquivo original e usa apply_theme em native_deck.py.
 * @module theme
 */

/**
 * Faz merge recursivo sem modificar base ou patch.
 * @param {object} base Padrões ou configuração de menor precedência.
 * @param {object} patch Overrides. Arrays substituem o array completo.
 * @returns {object} Cópia independente. result acumula os valores; objetos
 * aninhados passam pela mesma regra e valores escalares prevalecem diretamente.
 */
export function merge(base, patch = {}) {
  const result = structuredClone(base);
  for (const [key, value] of Object.entries(patch)) {
    result[key] = value && typeof value === 'object' && !Array.isArray(value)
      ? merge(result[key] || {}, value) : structuredClone(value);
  }
  return result;
}

/** Tokens extraídos da referência: cores hex sem #, tipografia em pt, espaço em in. */
export const brand = {
  colors: {
    primary: 'EC111A', text: '1E1117', muted: '666666', paper: 'FFFFFF',
    surface: 'F5EFE8', border: 'D8D6CA', neutral: 'BCB8A4',
    complete: '0070C0', inProgress: 'D8D6CA', notStarted: 'EEEEEB',
    majorIssues: 'EC111A', atRisk: 'FDB913', onTrack: '00A467',
  },
  fonts: { body: 'Scotia', heading: 'Scotia Headline', fallback: 'Arial' },
  type: { title: 21, body: 10.5, small: 9, caption: 7.5, kicker: 8 },
  spacing: { marginX: 0.56, marginY: 0.26, gap: 0.12, padding: 0.12 },
  line: { thin: 0.5, regular: 0.8, emphasis: 1.1 },
};

/** Configuração adaptativa: canvas 16:9, grid 14×9 e regiões comuns do template. */
export const defaults = {
  slide: { width: 13.333333, height: 7.5 },
  grid: { columns: 14, rows: 9, gapX: 0.12, gapY: 0.10 },
  theme: brand,
  // Native master objects cover shared chrome; template functions compose dynamic content.
  template: {
    headerRows: 1.35, footerRows: 0.55,
    showNumber: true, showLogo: true, showGrid: false,
    header: {}, footer: {},
  },
  components: {},
  templates: { executionDashboard: { showLogo: false } },
  assets: {},
  slides: {},
  elements: {},
};

/**
 * Resolve overrides adaptativos e valida invariantes antes de renderizar.
 * @param {object} patch Overrides de tokens, templates, componentes ou elementos.
 * @returns {object} Configuração independente dos defaults.
 * width/height são polegadas; headerRows/footerRows são tracks fracionários.
 * Um canvas fora de 16:9 ou regiões sem corpo falham de forma explícita.
 */
export function configure(patch = {}) {
  const config = merge(defaults, patch);
  const { width, height } = config.slide;
  if (!(width > 0 && height > 0) || Math.abs(width / height - 16 / 9) > 1e-5)
    throw new Error('Slides must use the 16:9 aspect ratio.');
  for (const color of Object.values(config.theme.colors))
    if (!/^[A-Fa-f0-9]{6}$/.test(color)) throw new Error(`Invalid brand color: ${color}`);
  if (!(config.template.headerRows > 0 && config.template.footerRows > 0 &&
      config.template.headerRows + config.template.footerRows < config.grid.rows))
    throw new Error('Header and footer must leave a positive content region.');
  return config;
}
