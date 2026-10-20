# Perfil de revisão e consistência

`npm run build` gera `output/recreated-slides.pptx` a partir de `config.quality.json`. A referência não é modificada. `npm run build:quality` também grava `output/reviewed-slides.pptx`. O perfil é opt-in na API: `await build({ quality: {} })`. O caminho sem revisão continua disponível em `npm run build:fidelity`.

## Tokens e unidades

| Papel | Mínimo | Alvo padrão | Máximo |
|---|---:|---:|---:|
| title (fallback sem referência) | 22 pt | 22 pt | 24 pt |
| body | 12 pt | 12 pt | 16 pt |
| dense | 10 pt | 10 pt | 12 pt |
| note | 8 pt | 8 pt | 9 pt |

`dense` identifica tabelas, matrizes, organogramas, anotações de cronogramas, rótulos de figuras e gráficos. A lista explícita `diagramRoles` em `src/quality.mjs` registra as exceções semânticas; ela pode ser substituída por `quality.roles`. Prosa usa `body`; referências e rodapés usam `note`. Fontes do perfil são materializadas nos runs, em vez de depender da substituição silenciosa de Scotia por outro renderizador. Arial é o padrão; `quality.font` seleciona outra família. As métricas preventivas são Arial; outra família exige nova revisão visual com a fonte instalada.

Fontes são pontos; `box` é polegadas; `grid` usa tracks fracionários. `spacing.tablePadding` é pontos, como a API PptxGenJS. As margens dos textos nativos são limitadas pela altura útil, evitando a área negativa que invertia textos. O espaçamento entre linhas é 110% no corpo e 100% em tabelas/diagramas. Células vazias mantêm um parágrafo estrutural invisível, sem herdar a fonte grande do master. `spacing.gap` controla o espaço entre cards do roadmap; `quality.elements` controla caixas, margens e estilos individuais dos componentes recompostos. Os valores padrão estão documentados em `qualityDefaults`.

## Aumentar fontes com controle

```json
{
  "quality": {
    "type": {
      "body": { "min": 12, "size": 14, "max": 16 },
      "dense": { "min": 10, "size": 10, "max": 12 }
    },
    "strict": true
  }
}
```

`size` precisa estar entre `min` e `max`. Os textos de conteúdo recebem o alvo do papel correspondente. As novas primitivas usam os tokens de conteúdo; títulos de cards e cabeçalhos usam os tokens compartilhados da hierarquia. Um override individual pode escolher outra fonte dentro do intervalo. A regra é começar no tamanho padrão e mantê-lo se couber. Com `quality.fontFit.enabled: true` (padrão), o motor reduz em passos de `quality.fontFit.step` (0,25 pt) até caber, respeitando o mínimo. Não aumenta automaticamente até `max` só porque existe área livre. A redução vem antes de aumentar caixas ou criar continuações. Tabelas reduzem como um conjunto, mantendo fonte uniforme entre células. O perfil não depende do autofit do leitor e não reduz abaixo dos mínimos. Se ainda não couber no mínimo, o motor tenta o reflow permitido ou a continuação configurada; na ausência de uma solução, termina com o ID responsável. Amplie a região ou recomponha o componente. Não é seguro aumentar todas as fontes mantendo todas as caixas fixas.

`quality.strict: false` é apenas para diagnóstico: exporta as pendências em `quality.estimatedOverflow`; não é o padrão de entrega. A auditoria estima alturas com avanços reais Arial, considera quebras explícitas, células mescladas e margens. Não equivale a uma garantia de renderização em todo leitor de PPTX.

## Configurar componentes recompostos

Os IDs são semânticos e estáveis: `10.agenda`, `23.timeline`, `29.governance`, `34.comparison`, `40.mix-0`, `40.kpi-0`, `58.tactics`, `65.card-title-0-0`, etc. A lista completa está em `report.quality.tokens.roles` e os objetos exportados usam nomes `custom.<id>`.

```json
{
  "quality": {
    "elements": {
      "31.notes-left": {
        "box": { "x": 0.56, "y": 5.2, "w": 6.02, "h": 1.05 },
        "style": { "fontSize": 12 }
      },
      "40.mix-0": {
        "style": { "chartColors": ["EBDFD1", "BCB8A4", "B10D13", "EC111A"] }
      }
    },
    "roles": { "31.custom.notes-left": "body" }
  }
}
```

Cada declaração aceita `box` ou `grid`, `style` nativo do PptxGenJS e seu conteúdo (`text`, `rows` ou `series`). Em `grid`, defina `col`, `row`, `colSpan`, `rowSpan`; a contagem vem de `config.grid`. Tabelas usam `style.colW`, `style.rowH` e `rows` com opções por célula. Gráficos usam `series: [{ name, labels, values }]`, com opções nativas em `style`. O importador copia relações, workbooks e tipos de conteúdo; não copia somente o quadro do gráfico.

Para objetos preservados, continue usando `elements['slide.eID']`. A normalização tipográfica ocorre depois desses patches e a escala por papel prevalece. IDs de novos objetos não precisam ser números sequenciais: use `quality.elements` para recompostos. Use `quality.repairSlides` para escolher quais construtores executar; todos os slides selecionados ainda recebem a normalização.

## Continuação e ordem de leitura

Os resumos 5 e 8 usam uma reserva de altura de 12% (`quality.paginationSafety: 1.12`) e são divididos por parágrafo, sem perder runs, ênfases ou palavras. Cabeçalhos de seção acompanham o parágrafo seguinte. As páginas extras entram imediatamente após a origem, mantendo seu master/layout. O título identifica as continuações. O manifesto conserva o número de origem; campos automáticos de numeração do Office podem exibir a posição final no deck. O manifesto distingue número original e parte OPC. O deck padrão passa de 71 para 73 páginas; o slide 68 fica visível no perfil de revisão.

A agenda mantém todas as atividades, inclusive o cocktail das 19:00. A governança mantém pessoas e mandatos. A comparação mantém avaliações de capacidade como texto e cor. O roadmap mantém os objetivos, substituindo ícones decorativos que dependiam de fontes incompatíveis por células com títulos. A timeline 23 mapeia horizontalmente as barras originais para uma nova coluna e dimensiona as linhas pelos entregáveis. As células e barras são objetos Office editáveis.

## Gráficos e verificação

Os 26 gráficos ativos são nativos. Os slides 31 e 40 são recompostos por `addChart` com os valores numéricos extraídos da referência a cada build. Os outros gráficos recebem categorias explícitas quando ausentes e fontes padronizadas, mantendo seus dados e geometrias. Dados de clientes do slide 31 são convertidos de pessoas para milhões, conforme a unidade do título. Nenhum gráfico é substituído por PNG/SVG.

`npm test` cobre limites de fonte, recusa de aumentos impossíveis, agenda sem duplicação, preservação de narrativa nas continuações e workbooks dos gráficos gerados. `npm run verify` confere o pacote final, relações internas, proporção, contagens e diagnóstico. `npm run docs:check` verifica documentação inline das funções. A validação de igualdade de pixels do baseline antigo não é um critério de qualidade deste perfil; a revisão visual deve verificar legibilidade e alinhamento do novo layout.


### Hierarquia padrão compartilhada

`quality.hierarchy.enabled: true` transforma a hierarquia identificada na referência em tokens comuns a todos os slides. Os valores da referência permanecem no catálogo para auditoria e classificação; o tamanho efetivo é o token do nível. Assim, os títulos de 22, 22,01 e 24 pt passam a usar o mesmo padrão de 22 pt. Diferenças acidentais entre elementos equivalentes deixam de ser reproduzidas.

| Token em `hierarchy.sizes` | pt | Aplicação |
|---|---:|---|
| title | 22 | Título principal de slide; também nos masters e layouts |
| subtitle | 14 | Subtítulo estrutural |
| section | 11 | Cabeçalho de seção |
| component | 12 | Título de card/componente e identificação de grupo |
| chartTitle | 10 | Título de gráfico ou cabeçalho compacto |
| tableHeader | 10 | Primeira linha das tabelas nativas |
| kicker | 10 | Identificação estrutural superior |
| statement | 16 | Declaração de destaque |
| display | 18 | Título de pilar estratégico |

O nível é explícito nos componentes recompostos; nos objetos preservados, o motor identifica os títulos e cabeçalhos a partir de placeholders, geometria, negrito e escala original. `quality.hierarchy.roles["slide.eID"]` ou `["slide.custom.id"]` permite corrigir/definir a função semântica. Novos elementos devem receber um nível explícito quando forem estruturais. O relatório grava `typographyRole`, `resolvedFontSize` e `referenceLocked`, permitindo comparar elementos equivalentes entre slides.

```json
{
  "quality": {
    "hierarchy": {
      "sizes": { "title": 22, "component": 12, "section": 11 },
      "roles": { "65.custom.card-title-0-0": "component" }
    }
  }
}
```

Alterar um token atualiza todos os elementos do mesmo nível. Títulos/cabeçalhos não reduzem automaticamente: falta de espaço requer ajuste de layout. O conteúdo mantém os padrões de corpo 12 pt, tabelas/gráficos 10 pt e notas 8 pt, com redução controlada até o mínimo configurado. Elementos estruturais usam `hierarchy.sizes`; `quality.elements.style.fontSize` não contorna esse padrão. Para uma exceção intencional, crie um novo token em `hierarchy.sizes` e associe o elemento em `hierarchy.roles`.

`quality.hierarchy.enabled: false`, combinado a `referenceTypography.enabled: true`, conserva os tamanhos individuais da referência, como no perfil anterior. Desativar ambos usa a escala genérica de `quality.type`. A família continua em `quality.font`.

### Caixas dinâmicas, elementos ligados e rodapé

`quality.flow.enabled` ativa o planejamento geométrico antes de normalizar as fontes. `boxPadding` (0,06 in) mede as faixas e os blocos; `footer.top` (6,80 in), `footer.bottom` (7,32 in) e `footer.gap` (0,14 in) definem a região exclusiva do rodapé e sua distância do conteúdo. O topo real da logo herdada também limita o conteúdo. Referências longas são medidas a 8 pt e recebem altura própria, com largura que termina antes da logo.

Faixas superiores com texto/fundo na mesma forma são medidas incluindo o tracking (espaço entre letras). A largura cresce com o texto e desloca as faixas seguintes. Se a largura total disponível terminar, a faixa passa a múltiplas linhas e o fundo cresce em altura. Rótulos verticais crescem no eixo da leitura. Fixar tamanhos tipográficos não remove a margem esquerda que reserva espaço aos ícones.

`quality.flow.stacks["45"]` declara pilhas de componentes através de `ids` (IDs dos blocos principais) e `right` (limite direito dos elementos ligados). Cada linha recebe a altura necessária ao texto. Ícones, linhas e anotações cujo centro pertence à linha acompanham o deslocamento. O motor distribui os espaços livres existentes sem reduzir as fontes estruturais; se o mínimo necessário exceder a região, gera erro em vez de empilhar conteúdo sobre o próximo componente. O relatório registra os ajustes em `quality.layoutConstraints`.

O padding das tabelas densas é 2 pt, comum ao perfil. O quadro é limitado à região de conteúdo e as alturas das linhas são novamente calculadas pelo texto. O modo sem revisão continua preservando o original.

`quality.flow.tableHeaders["38.e9"]` reserva altura mínima (`minHeight`, em in) e âncora (`anchor`, enum DrawingML) para cabeçalhos com logos sobrepostos ao quadro. O espaço da primeira linha inclui logos e texto; as outras linhas usam o restante da área disponível. O padrão do benchmark 38 é 0,72 in e texto na base (`b`), separando os nomes das imagens dos bancos.

`flow.footer.auxiliary` registra textos funcionais do rodapé por número de slide e nome do objeto (por exemplo, `65: ["custom.appendix"]`). Esses textos mantêm o tamanho de rótulo denso, ficam na área reservada e terminam antes da logo; o motor não os desloca para cima dos cards.


### Ícone antes do texto em tabelas

`quality.flow.tableIcons["58.custom.tactics"]` define a coluna reservada ao ícone (`column: 1`), a coluna do texto (`textColumn: 2`), o tamanho quadrado (`size: 0.32`, em in) e o espaço até o texto (`gap: 0.12`, em in). `prefix` identifica o conjunto de peças e `kinds` permite escolher os símbolos por linha: youth, winter, team, inbound, outbound, pricing, wealth, engagement. Os ícones são formas Office editáveis e não usam fontes de símbolos nem imagens rasterizadas.

A tabela do slide 58 inclui uma coluna vazia dedicada. Depois de calcular as alturas finais das linhas, `anchor_table_icons` centraliza cada conjunto verticalmente e posiciona sua borda direita a exatamente `gap` do começo do texto, incluindo o padding da célula. Todas as linhas usam o mesmo tamanho e afastamento. O relatório registra os oito anchors em `quality.layoutConstraints["58"].tableIcons`, para verificar as distâncias numericamente. Falta de largura/altura ou gap negativo interrompem a geração.


### Padding de painéis e área útil

`quality.flow.panelPadding: 0.12` define o recuo mínimo (em in) para textos contidos em fundos independentes. O motor escolhe o menor container preenchido que contém o texto e calcula a área útil após descontar o padding. `boxPadding: 0.06` continua sendo o padrão dos componentes compactos.

`quality.flow.panels["52"]` declara os cinco painéis do roadmap: `padding` nas quatro bordas, `gap` entre ícone/título/corpo, `paragraphGap` entre iniciativas, `markerLane` reservado aos indicadores e `markerGap` até o texto. Os corpos começam na mesma linha. Títulos usam o token component e descrições usam dense; a lista é medida com sua largura útil, preservando ênfases e palavras. Os bullets nativos duplicados são removidos porque os indicadores coloridos ocupam uma faixa própria.

Os marcadores acompanham a altura real de cada parágrafo, por `anchor_paragraph_markers`. O limite inferior do corpo preserva o padding até a base do painel, mesmo que exista espaço antes do footer. `labels` alinha os rótulos à esquerda sem invadir a primeira coluna. `legend` posiciona os indicadores Retail/iTRADE em linha no rodapé, com espaço separado até os rótulos e até a logo. A medição registra `paragraphHeights`; os ajustes aparecem em `quality.layoutConstraints`.

### Cards de prioridades (slide 51)

`quality.flow.cards["51"]` associa grupos nativos aos títulos, números, descrições e responsáveis, em ordem de leitura. `padding` (0,12 in) recua o conteúdo das quatro bordas; `compactPadding` (0,06 in) protege os nomes dentro de seus boxes. `internalGap` (0,04 in) separa boxes e blocos internos; `gap` (0,12 in) separa os cards. `badgeSize` e `badgeGap` reservam a faixa do número antes do título.

`layout_cards` mede os títulos pela fonte e pelo tracking, mantém a mesma faixa de cabeçalho nos oito cards e calcula cada altura de responsável pelo número de linhas. Os responsáveis são alinhados à base com padding constante; o corpo usa somente a área restante. `bannerTop`, `bannerHeight` e `columns` controlam a região e a grade. A área inferior respeita o footer; falta de espaço interrompe a geração com o ID do card. Todos os elementos continuam editáveis.

### Ícones acima do texto (slide 71)

`quality.flow.iconCards["71"]` associa cada shape original à dupla de shapes vetoriais do ícone. `layout_icon_cards` separa o fundo, o primeiro parágrafo (título) e os bullets em objetos nativos editáveis, conservando o conteúdo. Isso evita depender do inset superior original, que era perdido na normalização tipográfica.

`padding: 0.12`, `gap: 0.12`, `paragraphGap: 0.07` e `iconSize: 0.432` estão em polegadas. O maior título determina uma faixa de cabeçalho comum; todos os corpos começam na mesma linha e respeitam a base do card. Títulos usam component (12 pt) e bullets dense (10 pt). O relatório `layoutConstraints` registra os limites das áreas e seus IDs.

### Padding global de containers nativos

`inset_container_text` cobre tanto fundos independentes quanto shapes que carregam seu próprio texto. Os primeiros recebem geometria interna; os segundos recebem margens explícitas no text body, evitando duplicar o recuo. Painéis com altura a partir de 0,8 in usam `flow.panelPadding` (0,12 in); boxes compactos usam `flow.boxPadding` (0,06 in). Tabelas preservam o token próprio de 2 pt. Faixas reservadas a ícones são mantidas.

`flow.iconCards["64"]` separa ícone, título de dois parágrafos e descrição nos cards Simple/Complex. `headingParagraphs` ignora parágrafos vazios e mede a altura total do título; os dois cards usam o mesmo cabeçalho. `flow.textHierarchy` mapeia parágrafos para tokens nos cards densos dos slides 24 e 28, preservando a distinção de título/nome e descrição. A falta de espaço continua interrompendo o build.

### Capas e divisórias

As capas da referência usam placeholders `body`, e não `title`. `prepareQuality` identifica os títulos com tamanho original a partir de 48 pt e posição abaixo de 2 in, atribuindo os níveis `coverTitle` (60 pt na capa inicial) e `sectionCoverTitle` (66 pt nas divisórias). A numeração usa `coverNumber` (28 pt). Subtítulo inicial usa statement (16 pt); a data usa subtitle (14 pt). Os tokens são configuráveis em `quality.hierarchy.sizes`, e overrides por elemento prevalecem.

O adaptador mantém a fonte da capa fixa e amplia a altura do texto quando ele precisa quebrar em linhas, respeitando a área útil. Não reduz a capa para o token de conteúdo de 22 pt. Remove somente parágrafos vazios do título para evitar linhas fantasma. Os placeholders correspondentes dos layouts recebem os mesmos tokens, para reutilização das capas.

### Revisão no Keynote e regiões vinculadas

As faixas superiores agora usam exatamente a largura medida do texto (Arial, peso e tracking), mais duas vezes `boxPadding`; a largura original não funciona como mínimo. As duas partes são posicionadas em sequência e compartilham altura pelo token kicker. Isso permite que WEALTH, ALL BANK e COUNTRY OVERVIEW tenham larguras distintas, com o mesmo padding.

`flow.regions` limita textos à área útil de cada componente. `calloutRows` mede texto rico e reserva a faixa dos ícones; `legends` associa o retângulo e seu rótulo com gap explícito; `numbered` reserva uma faixa exclusiva para badges antes dos parágrafos. `elements` controla box, inset, tokens de parágrafo, remoção de vazios e limite inferior. O rodapé também reconhece notas extensas numeradas, evitando que a nota de risco invada o painel lateral.

`table_overlay_cells` e `anchor_table_overlays` vinculam destaques de valores às células antes de redistribuir as alturas, mantendo os contornos centralizados. `materialize_vertical_table_labels` conserva rótulos como Tailwinds, Headwinds, Loans e Deposits em text boxes editáveis rotacionados sobre a mesma área da célula; o Keynote não preserva a orientação desses textos dentro de células. O texto é transferido, sem duplicação, e o fundo/merge permanece na tabela nativa.

`scripts/chart_compat.py` corrige o range inválido emitido por PptxGenJS 4.0.1 ([issue 1531](https://github.com/gitbrent/PptxGenJS/issues/1531)) e células numéricas vazias referentes a zero. Para os workbooks XLSB de gráficos antigos, gera um XLSX portátil a partir dos caches e das fórmulas do próprio gráfico. Séries, valores, estilos e os gráficos Office permanecem nativos. `workbookRepairs` registra os arquivos alterados; o perfil fidelity não passa por essa conversão.

`npm run verify:keynote` abre somente uma cópia temporária no Keynote, conta os slides e os gráficos nativos, exporta um PDF privado e grava hash/versão em `output/review/keynote/review-report.json`. Não salva ou fecha documentos que o usuário já tinha abertos. A inspeção visual do PDF é necessária além da contagem; a importação do Keynote difere da do LibreOffice.
