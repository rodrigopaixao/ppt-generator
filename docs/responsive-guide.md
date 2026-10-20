# Biblioteca de slides em PptxGenJS

Reconstrução editável dos slides **5, 10, 21, 38, 50, 64 e 68** do arquivo de referência. O original permanece intacto.

## Executar

Node.js 20+ e Python 3 para extração e verificação.

```sh
npm install
npm run build:responsive
npm test
npm run verify
```

No ambiente Codex, o gerador também encontra as dependências locais do runtime quando `node_modules` não existe. É possível indicar outro diretório com `CODEX_NODE_MODULES`.

O resultado fica em `output/responsive-slides.pptx`. O slide de origem 68 mantém o estado oculto do original. Para exibir os sete slides e usar Arial explicitamente:

```sh
node src/generate.mjs --mode responsive --font Arial --show-hidden --output output/preview-arial.pptx
```

**As fontes Scotia e Scotia Headline devem estar instaladas para a tipografia de marca.** Não estão incorporadas no arquivo de referência e não são distribuídas aqui. A seleção de Arial é uma substituição explícita para prévia. As medidas de texto usam métricas Arial com margem de segurança, portanto a validação final com as fontes Scotia continua necessária.

## Grid e responsividade

“14:9” significa **14 colunas × 9 linhas**, configuráveis, dentro de um canvas **16:9**. São conceitos independentes. O aspecto do slide é validado e preservado quando suas dimensões mudam.

```sh
node src/generate.mjs --mode responsive --grid 12x8 --output output/grid-12x8.pptx
npm run build:debug
```

`Grid` determina as regiões de título, corpo e rodapé. Componentes recebem uma caixa disponível, dividem esse espaço por pesos e calculam as posições dos filhos. Coleções determinam quantas colunas cabem por largura mínima e por extensão mínima no grid, preenchem da esquerda para a direita e continuam de cima para baixo. A altura disponível se redistribui entre as linhas resultantes. Timelines usam datas para posicionar eventos, mantendo rótulos separados por faixa e cartões em ordem cronológica.

**A responsividade acontece ao gerar o PPTX.** PowerPoint recebe objetos com posições calculadas. Alterar texto manualmente no PowerPoint não executa novamente o motor de layout. Para redistribuir, altere os dados/configuração e gere novamente.

Textos e tabelas são medidos antes da geração. O motor reduz a fonte até o mínimo configurado e rejeita um layout que não acomode o conteúdo. Ele não corta conteúdo nem acrescenta slides automaticamente. Grids extremamente pequenos, textos muito extensos ou muitos componentes podem exigir ajustar o template ou os limites mínimos.

## Arquitetura

| Arquivo | Responsabilidade |
| --- | --- |
| `src/theme.mjs` | Tokens de marca, dimensões e configuração |
| `src/layout.mjs` | Grid, fluxo por pesos, quebra de linhas e caixas relativas |
| `src/components.mjs` | Texto, rich text, formas, imagens, tabelas nativas, painéis e gráficos nativos |
| `src/content.mjs` | Conteúdo e referências dos sete slides |
| `src/templates.mjs` | Sete templates, regiões e registro dos masters |
| `src/generate.mjs` | Preparação dos assets e geração |
| `scripts/extract.py` | Extração reprodutível de XML, notas, dados e artwork original |
| `scripts/verify.py` | Verificação do PPTX exportado e preservação do conteúdo |

Não há screenshots de slides como conteúdo. Textos, formas, diagramas, duas tabelas e três gráficos são editáveis. Ícones e logos reutilizam artwork extraído do original. Seus SVGs ficam em `assets/`, com PNGs de alta resolução para compatibilidade entre leitores de PowerPoint. Os ícones são imagens redimensionáveis, não formas vetoriais editáveis dentro do PowerPoint.

Os sete templates registram masters pela API `defineSlideMaster`. PptxGenJS os exporta como layouts reutilizáveis ligados ao master compartilhado. O master contém o chrome estático. Títulos, conteúdo, fontes e número de origem ficam nos slides, pois variam por instância. Não se trata de sete masters independentes do tipo `<p:sldMaster>`.

## Configuração

```sh
node src/generate.mjs --mode responsive --config config.example.json
```

`config.example.json` demonstra as camadas. A precedência é:

1. Tokens e padrões da biblioteca.
2. Configuração global do componente em `components`.
3. Configuração da instância de template em `templates`.
4. Configuração do componente por slide em `slides.<origem>.components`.
5. Configuração de cada elemento em `elements.<origem>.<id>`.

Objetos fazem merge recursivo. Arrays são substituídos por inteiro. `slides.<origem>.data` permite alterar conteúdo, dados e quantidade de itens sem editar o layout.

```json
{
  "grid": { "columns": 14, "rows": 9 },
  "theme": {
    "colors": { "primary": "EC111A", "surface": "F5EFE8" },
    "fonts": { "body": "Scotia", "heading": "Scotia Headline" }
  },
  "components": {
    "strategicPillars": { "gap": 0.24, "minWidth": 2.2, "minColumnSpan": 3 }
  },
  "templates": {
    "executionDashboard": { "showLogo": false, "headerRows": 1.35 }
  },
  "elements": {
    "50.pillars.items.0.title": {
      "text": "Grow in priority markets", "fontSize": 18, "align": "center"
    },
    "64.journey.0.steps.0.circle": { "visible": false }
  }
}
```

Cada elemento aceita `visible` e `box` (`x`, `y`, `w`, `h`, em polegadas). Textos aceitam `text`, `fontSize`, `minFontSize`, `padding`, `leading`, estilo e opções PptxGenJS. Formas aceitam `type`, `line` e `fill`. Imagens aceitam `asset`. Tabelas aceitam `values`, `weights`, `rowStyles`, `cellStyles` e `pptx` para opções nativas adicionais. Gráficos aceitam `series`, `holeSize`, `firstSliceAng` e `pptx`. Uma substituição manual de `box` é uma opção avançada que prevalece sobre o layout calculado.

Os IDs estão em `output/responsive-slides.layout.json`, junto com caixas, tamanhos de fonte e conteúdo. Cada objeto também recebe um nome identificável no PPTX. Os objetos estáticos do master podem ser configurados com `templates.<nome>.masterObjects`, `master` e `logo`.

Os tokens foram extraídos da apresentação. Eles não substituem um manual oficial de marca. Artwork oficial de logos permanece inalterado. Ícones extraídos seguem os tokens de cor e podem receber substituição em `assets`:

```json
{ "assets": { "assets/source-50-geometry-4.svg": { "path": "assets/meu-icone.svg", "tint": "EC111A" } } }
```

## Verificação e fidelidade

`npm test` cobre limites do grid, ordem de leitura, reflow, conteúdo adicional, ajuste de fontes, outra dimensão 16:9, outro grid e overrides. `npm run verify` abre o ZIP exportado e verifica contagem, aspecto, tabelas e gráficos nativos, valores dos gráficos e preservação dos textos principais.

Esta implementação adapta os layouts ao motor responsivo. Não é uma conversão pixel a pixel das coordenadas originais. Espaços usados manualmente para posicionamento foram normalizados. A timeline preserva os dois rótulos “SteerCo #4” presentes no original. No dashboard, o quarto valor de cada rosca é o espaçador que cria o semicírculo, não um indicador adicional.

Para renderizar uma prévia dos sete slides com LibreOffice e Poppler disponíveis:

```sh
node src/generate.mjs --mode responsive --font Arial --show-hidden --output output/review/slides-visible.pptx
soffice --headless --convert-to pdf --outdir output/review output/review/slides-visible.pptx
pdftoppm -scale-to 1400 -png output/review/slides-visible.pdf output/review/slide
```

A prévia usa uma fonte alternativa. A revisão com a fonte de marca deve usar uma máquina com Scotia instalada.
