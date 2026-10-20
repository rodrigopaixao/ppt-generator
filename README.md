# Repositório de slides configuráveis

O build padrão agora aplica o **perfil de revisão** aos 71 slides de origem. A saída tem **73 páginas**: os resumos dos slides 5 e 8 têm continuação para preservar todo o texto com corpo de 12 pt. O canvas continua 16:9 e o grid configurável é 14 colunas × 9 linhas.

A escala é centralizada em `config.quality.json`: corpo **12–16 pt** (alvo 12), tabelas/diagramas/gráficos **10–12 pt** (alvo 10), notas **8–9 pt** (alvo 8) e títulos/cabeçalhos **fixos por nível semântico** em `quality.hierarchy` (título 22 pt, seção 11 pt, componente 12 pt, gráfico/tabela 10 pt). A geração falha se uma alteração de fonte ultrapassar os limites ou se o texto não couber. Os gráficos permanecem nativos e editáveis; os seis gráficos recompostos dos slides 31 e 40 incluem workbooks XLSX gerados pelo PptxGenJS.

A revisão recompõe agenda (10), cronograma (23), governança (29), indicadores/gráficos (31 e 40), comparação (34), táticas (58) e roadmap (65). Os demais slides recebem normalização tipográfica, correções de margens e ajustes pontuais. Arial é o padrão portátil desse perfil; pode ser trocada pela fonte oficial quando instalada. Cores, imagens de marca, layouts e masters originais continuam disponíveis.

Veja [o guia de revisão](docs/quality.md) para controlar os tokens, aumentar fontes, editar os novos componentes e entender a validação.
## Gerar

```sh
npm install
npm run build
npm run verify
npm test
npm run docs:check
```

O resultado fica em `output/recreated-slides.pptx`. A referência `2606 Context Enriched Slide Repository.pptx` é uma dependência do build e permanece intacta. No Codex, os pacotes instalados no runtime podem ser usados offline se `node_modules` não existir.

## Fidelidade

A API `build()` sem `quality` e `npm run build:fidelity` preservam os objetos DrawingML originais. **Não é uma reimplementação exclusivamente em chamadas addShape/addText**: PptxGenJS gera o pacote intermediário, layouts e objetos novos; o adaptador conserva XML, temas, tabelas, gráficos, grupos, recursos, notas e relações que a biblioteca não importa sem perdas. Nenhum slide é transformado em screenshot.

No baseline de `build:fidelity` sem overrides, todas as partes visuais e recursos são byte a byte iguais aos da referência. Apenas os metadados de autoria são atualizados. A revisão de renderização dos **71 slides** encontrou **71 correspondências exatas de pixels**, no mesmo LibreOffice, mesmas fontes e resolução de 960 px. O slide 68 foi exposto em cópias de ambas as apresentações para entrar na revisão, e permanece oculto nesse baseline. O perfil de revisão expõe o slide 68 para inspeção.

As fontes Scotia não estão incorporadas no original. A comparação verifica a mesma renderização das duas apresentações neste ambiente; não certifica a instalação das fontes oficiais nem resultados em qualquer outro renderer. O baseline mantém as declarações de fonte originais. O perfil de revisão usa a família explícita de `quality.font`.

## Configurar

```sh
node src/generate.mjs --config config.fidelity.example.json
node src/generate.mjs --slides 5,10,21,38,50,64,68 --output output/selection.pptx
node src/generate.mjs --show-hidden --output output/all-visible.pptx
```

O catálogo `data/templates.json` lista as 71 variantes reutilizáveis, de `source-001` a `source-071`. Cada uma aponta para seu layout e master reais. Os IDs de objetos estão em `data/slides/NNN.json`. Exemplo de edição nativa:

```json
{
  "grid": { "columns": 14, "rows": 9 },
  "elements": {
    "5.e5": {
      "text": "Novo resumo executivo",
      "textStyle": { "fontSize": 19, "fontFace": "Scotia Headline" }
    }
  },
  "slides": {
    "10": {
      "elements": {
        "e8": { "table": { "cells": { "1.2": { "text": "Nova atividade" } } } }
      }
    }
  }
}
```

Os IDs são nativos e estáveis dentro da referência. `e5` no slide 5 é diferente de `e5` em outro slide. O número antes do ponto é o número do slide original. A ordem de execução é: tokens, masters, layouts, slides, overrides globais de elementos e adições PptxGenJS. As instruções completas estão em `docs/configuration.md` e no próprio código.

## Grid, responsividade e templates

O baseline de fidelidade mantém as coordenadas originais, representadas também em tracks fracionários no catálogo. Apenas mudar a contagem do grid não move automaticamente o original: fazê-lo destruiria a referência visual. Use `grid` por objeto para posicionar no novo grid e `flows` para distribuir coleções da esquerda para a direita, continuando de cima para baixo. Grupos mantêm seus filhos, escalas e hierarquia.

A redistribuição acontece na geração. Editar manualmente um PPTX não executa o motor JavaScript/Python. Textos e quantidades diferentes podem exigir ajustar caixas, limites e fluxos. Igualdade visual com o original se refere ao baseline sem alterações de conteúdo ou estilo.

Os **sete templates semânticos adaptativos** anteriores continuam disponíveis:

```sh
npm run build:responsive
node src/generate.mjs --mode responsive --config config.example.json
```

Eles reorganizam conteúdo e ajustam fontes; não prometem igualdade visual com a referência. O guia está em `docs/responsive-guide.md`. O modo fiel é o que cobre os 71 slides.

## Código e documentação inline

| Arquivo | Responsabilidade |
| --- | --- |
| `src/quality.mjs` | Tokens, composição dos layouts revistos e limites de fonte |
| `scripts/quality_deck.py` | Normalização, medição, categorias nativas e paginação |
| `src/generate.mjs` | API pública, CLI, scaffold PptxGenJS e adições |
| `scripts/native_deck.py` | Preservação, catálogo, herança, transformações, overrides e XLSX |
| `src/layout.mjs` | Grid e fluxo adaptativo |
| `src/theme.mjs` | Tokens e configuração dos templates semânticos |
| `src/components.mjs` | Componentes editáveis do modo adaptativo |
| `src/templates.mjs` | Sete composições semânticas |
| `src/responsive.mjs` | Gerador adaptativo |
| `scripts/verify.py` | Auditoria independente do pacote exportado |
| `scripts/visual_review.py` | Comparação de pixels de todas as páginas |
| `scripts/check_docs.py` | Verificação de documentação das funções nomeadas |

As funções têm JSDoc/docstrings com finalidade, entradas, unidades, retorno, variáveis relevantes, algoritmo e efeitos. Callbacks pequenos são explicados pelo contexto da função. `npm run docs:check` audita funções nomeadas, métodos e helpers, sem confundir presença de comentário com prova de qualidade.

## Verificação visual reproduzível

```sh
npm run verify:visual
```

Requer LibreOffice, Poppler e Pillow. A revisão grava PDFs, PNGs, seis contatos e `visual-report.json` em `output/review/full/`. Essas imagens são evidência de QA, não conteúdo dos slides. `npm run verify` não exige ferramentas de renderização.
