# Documentation

This documentation describes the repository's implemented behavior, parameters, and limitations. The source contains 71 slides; the default quality profile produces 73 pages; the semantic responsive implementation covers seven source slides.

## Reading paths

Start with [Getting started](getting-started.md) and [Architecture](architecture.md). For full-deck customization, read [Native configuration](configuration.md) and [Quality](quality.md). For reusable layouts, read [Components](components.md), [Templates](templates.md), and the [Responsive guide](responsive-guide.md).

| Document | Questions it answers |
| --- | --- |
| [Getting started](getting-started.md) | What should I install and run? Where are the results? |
| [Architecture](architecture.md) | Why JavaScript and Python? How do native resources survive? |
| [Native configuration](configuration.md) | How do I edit existing elements and add new ones? |
| [Quality and consistency](quality.md) | Which typography and spacing rules are enforced? |
| [Components](components.md) | What does each public primitive accept and return? |
| [Templates and masters](templates.md) | Which families exist and what content do they expect? |
| [Responsive guide](responsive-guide.md) | How are tokens, grids, assets, and overrides combined? |
| [API and CLI](api.md) | How do I invoke the generator from code or automation? |
| [Validation](validation.md) | How do I detect overflow and reader-specific issues? |
| [Extending](extending.md) | How do I introduce a component or repair recipe? |
| [Quality defaults](reference/quality-defaults.json) | What are all default values and source-specific bindings? |

## Terminology and units

| Term | Meaning |
| --- | --- |
| Source number | One-based original slide number; stable after pagination |
| Output page | Position in the exported deck; can differ from source number |
| Native element | Original DrawingML object, with an ID such as `e8` |
| Addition | New PptxGenJS object imported into a preserved slide; named `custom.<id>` |
| Template | A native source layout or a semantic responsive renderer; distinguished in each guide |
| Box | `{x,y,w,h}` in inches; origin at the slide's top-left |
| Grid | Configurable columns and rows, default 14 × 9; zero-based indices |
| Font size | Points; 72 points equal one inch |
| EMU | DrawingML coordinate unit; 914,400 EMU equal one inch |
| OPC part | A file inside the PPTX ZIP, such as slide XML or an embedded workbook |

All documentation here is English. Original presentation content and identifiers remain source data and are not translated as part of documentation maintenance.
