# Contrato de configuração

O contrato também está documentado no próprio código em `src/fidelity-config.mjs`. Todos os números de slide/IDs abaixo foram verificados no catálogo da referência.

## Escolher o mecanismo

A CLI sem configuração usa `fidelity` e cobre os 71 slides. `npm run build` agora fornece `config.quality.json`, que aplica o [perfil de revisão](quality.md) sobre esse mecanismo e cria continuações quando necessário. Ele mantém as partes nativas e não troca o original por screenshots. O arquivo original é uma dependência de build. `responsive` compõe os sete templates semânticos e usa o contrato antigo de `config.example.json`. Use `config.fidelity.example.json` no modo fiel. Não misture os dois contratos.

## Encontrar IDs e templates

`data/templates.json` contém 71 variantes (`source-001` a `source-071`). `data/slides/050.json`, por exemplo, descreve a variante do slide 50, os IDs, caixas, hierarquia e recursos. `data/catalog.json` inclui também os 148 layouts e 7 masters.

Os IDs são `e` seguido do ID nativo, não índices de arrays. A hierarquia é indicada por `parentId`. `box` é uma caixa em polegadas e `grid` é uma representação fracionária em 14×9; o original não sofre arredondamento para caber em tracks inteiros. `inheritedFrom` indica de onde veio a geometria. Estilos continuam na cadeia nativa de herança, em vez de serem achatados por aproximação.

O mesmo template de origem pode ser reutilizado em builds distintos com `selection` e dados diferentes. A seleção de um build aceita números únicos e preserva os IDs de origem.

## Precedência

1. Tema por tokens ou mapas explícitos.
2. Overrides de `masters.slideMasterN`.
3. Overrides de `templates.slideLayoutN`.
4. Overrides de `slides.<n>`.
5. Overrides de `elements.<n>.<eID>`.
6. Operações avançadas em `nativeParts`.
7. Objetos novos declarados em `additions`, gerados pelo PptxGenJS.

Dentro do slide, `flows` calcula as caixas; uma caixa explícita em `elements` prevalece. Configurações desconhecidas geram erro, em vez de serem tratadas como configurações aplicadas com sucesso.

## Texto, estilos e geometria

```json
{
  "elements": {
    "5.e5": {
      "text": "Novo resumo",
      "textStyle": {
        "fontFace": "Scotia Headline",
        "fontSize": 19,
        "color": "EC111A",
        "align": "left"
      },
      "grid": { "col": 1, "row": 1, "colSpan": 11, "rowSpan": 1 }
    }
  }
}
```

`text` substitui o corpo, usando o primeiro estilo como base. `textRuns` aceita índices de runs para preservar ênfases distintas. `textReplacements` opera dentro de cada run, sem atravessar fronteiras de formatação. `textStyle` aceita fonte, tamanho em pontos, negrito, itálico, cor, alinhamento, margem em polegadas, âncora vertical e wrap.

`box` usa polegadas globais. `localBox` usa EMU no espaço do pai, indicado para filhos de grupos rotacionados. `rotation` usa graus. `visible:false` remove o objeto da saída. As formas aceitam `fill`, `line` e `shapeType`. Geometria herdada só é materializada quando uma edição exige geometria própria.

## Fluxo responsivo

```json
{
  "slides": {
    "50": {
      "flows": [{
        "elements": ["e25", "e26", "e27", "e28"],
        "region": { "x": 1, "y": 2, "w": 5, "h": 4 },
        "minWidth": 2,
        "gap": 0.1
      }]
    }
  }
}
```

Esse exemplo redistribui especificamente os quatro textos de pilares em duas linhas; não move seus ícones. Para mover componentes inteiros, selecione seus grupos nativos apropriados. O motor não infere agrupamentos semânticos que não existam no original. Não inclua simultaneamente pai e filho no mesmo fluxo.

A área disponível determina quantas colunas cabem. A ordem da lista determina a leitura da esquerda para a direita e depois de cima para baixo. Fontes de texto não são recalculadas automaticamente pelo modo fiel. Para um novo volume de conteúdo, ajuste caixa/estilo ou use a composição semântica adaptativa quando houver template adequado. Alterações configuradas não mantêm, por definição, igualdade visual com o conteúdo anterior.

## Tabelas

```json
{
  "slides": {
    "10": {
      "elements": {
        "e8": {
          "table": {
            "cells": {
              "1.2": {
                "text": "Nova atividade",
                "fill": "F5EFE8",
                "textStyle": { "bold": true }
              }
            }
          }
        }
      }
    }
  }
}
```

Índices são base zero, incluindo a linha de cabeçalho. `rows` substitui a matriz mantendo a quantidade de colunas. Quando muda a quantidade de linhas, o motor clona a última e redistribui a altura total. Mesclas complexas podem requerer revisão específica. `columnWidths` e `rowHeights` recebem polegadas. O corpo continua sendo uma tabela PowerPoint editável.

## Gráficos

```json
{
  "slides": {
    "68": {
      "elements": {
        "e114": {
          "chart": {
            "series": [{ "values": [2, 7, 2, 11] }],
            "xmlPatches": [{ "path": ".//c:holeSize", "attributes": { "val": "60" } }]
          }
        }
      }
    }
  }
}
```

Mantém a quantidade de séries e pontos. `{}` preserva uma série. `name`, `labels`, `values`, `xValues` e `yValues` dependem do tipo original. O motor atualiza cache e XLSX incorporado, clonando os recursos por instância para não alterar outro slide. No dashboard, o último valor é o espaçador branco, não uma medida adicional.

Elementos auxiliares de texto desenhados fora do gráfico são objetos separados no original. Se mudar a informação desses elementos, configure também seus IDs; o adaptador não inventa relações semânticas entre textos soltos e séries de dados.

## Branding e imagens

`theme.colors` aceita primary, surface, paper e text. `theme.fonts` aceita body e heading. `theme.colorMap`/`fontMap` fazem substituições por valores exatos. Todos os temas da referência continuam disponíveis. Imagens e logos rasterizados não são recoloridos automaticamente.

Use `image` no objeto de imagem para fornecer outro arquivo local. A alteração mantém crop/geometria/efeitos, cria um recurso privado e atualiza o relacionamento. Substituições SVG recebem automaticamente um fallback PNG pelo wrapper JavaScript, mantendo também o vetor no PPTX. Para preservar o enquadramento visual, use a mesma proporção da imagem original. O baseline conserva inclusive SVG, EMF e WDP sem conversão.

## Masters, layouts e propriedades avançadas

`masters.slideMaster1` e `templates.slideLayout20` aceitam `elements` e `background`. IDs pertencem a essas partes, não ao slide. O efeito propaga pela herança original. Alterar um objeto diretamente no slide tem precedência sobre o valor herdado.

`xmlPatches` opera sobre um objeto; `chart.xmlPatches` sobre o gráfico privado; `nativeParts` sobre uma parte OPC inteira. Operações aceitam `path`, `attributes`, `text`, `remove` e `appendXml`. Use o prefixo correto e forneça namespaces no fragmento inserido. Essa é a saída para propriedades DrawingML sem equivalente no PptxGenJS, como ajustes especiais de geometria, eixos ou efeitos.

`additions` cria objetos novos via PptxGenJS. Cada declaração aceita `kind:text|shape`, `id`, `text`/`type`, `box`/`grid` e `style`. Objetos novos recebem nomes `custom.<id>` no painel de seleção.

## Resultados e limites de verificação

`output/recreated-slides.layout.json` identifica exatamente as partes alteradas. `baselineVisualPartsByteIdentical:true` significa que todas as partes visuais e binárias da referência foram mantidas, sem exceções ocultas. Para configurações que mudam conteúdo, o valor é false e `changedParts` mostra o efeito.

A comparação visual é feita no mesmo ambiente de renderização. Manter as declarações de fonte não instala nem incorpora uma fonte ausente. Fidelidade fora desse ambiente depende das fontes e do leitor usado, assim como no arquivo original.
