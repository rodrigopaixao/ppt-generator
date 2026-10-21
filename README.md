# Context Slide Components

An editable PowerPoint generator built with **PptxGenJS**, a configurable layout engine, and a Python DrawingML adapter. It recreates the 71-slide reference deck, standardizes typography and spacing, and provides seven reusable responsive templates. Slides use a **16:9 canvas**; the configurable **14 × 9 layout grid** is independent of that aspect ratio.

## Quick start

Requires Node.js 24+, npm, Python 3, and `2606 Context Enriched Slide Repository.pptx` in the project root.

```sh
npm install
npm run build
npm run verify
```

The default build writes `output/recreated-slides.pptx` and `output/recreated-slides.layout.json`. The current quality profile produces 73 pages, including continuations for source slides 5 and 8. Generated output is ignored by Git. The reference is never overwritten.

## Build modes

| Intent | Command | Behavior |
| --- | --- | --- |
| Consistent full deck | `npm run build` | Native preservation plus `config.quality.json` |
| Separate quality output | `npm run build:quality` | Same profile; writes `output/reviewed-slides.pptx` |
| Preserve source visual parts | `npm run build:fidelity` | 71 slides; explicit overrides only; source slide 68 remains hidden |
| Compose semantic components | `npm run build:responsive` | Rebuilds source slides 5, 10, 21, 38, 50, 64, and 68 |
| Inspect responsive geometry | `npm run build:debug` | Responsive build with grid and text bounds |

Quality is a profile of the fidelity engine, not a third CLI mode. The CLI without arguments uses fidelity; the npm default explicitly supplies the quality configuration. Responsive and native configurations have different contracts.

## Inline web editor

The repository also includes a Next.js/TypeScript editor and an AdonisJS API.
With Node.js 24+, run `npm ci` and `npm run dev`, then open
[Slide Studio](http://127.0.0.1:3000). Create a project, edit simple text directly
on a slide, and export an editable PPTX. See the [editor guide](docs/editor.md)
for preview dependencies, routes, persistence, limitations and tests.

## Documentation

Start with the [documentation index](docs/README.md). All guides and examples are in English.

| Guide | Contents |
| --- | --- |
| [Getting started](docs/getting-started.md) | Setup, commands, prerequisites, and outputs |
| [Architecture](docs/architecture.md) | Pipelines, module responsibilities, resource relationships, and diagrams |
| [Native configuration](docs/configuration.md) | Parameters for elements, text, tables, charts, images, flows, and XML patches |
| [Quality and consistency](docs/quality.md) | Typography, fitting, padding, dynamic boxes, footer clearance, and repair recipes |
| [Component API](docs/components.md) | Layout primitives, Canvas methods, composites, defaults, and return values |
| [Templates and masters](docs/templates.md) | Template families, content schemas, inheritance, and customization |
| [Responsive guide](docs/responsive-guide.md) | Branding tokens, override precedence, assets, and examples |
| [API and CLI](docs/api.md) | JavaScript entry points, CLI flags, environment variables, and manifests |
| [Validation and troubleshooting](docs/validation.md) | Tests, package checks, visual review, and Keynote compatibility |
| [Extension guide](docs/extending.md) | Adding components, templates, recipes, and maintaining the documentation |

## Development

```sh
npm test
npm run docs:check
```

Text, shapes, tables, and charts remain native editable Office objects where authored as such. Original artwork retains its media representation. Slide screenshots are not used as slide content. Responsiveness runs **at build time**: editing text in PowerPoint or Keynote does not rerun the layout engine.

Quality mode uses Arial by default. Responsive mode uses Scotia and Scotia Headline; install those fonts or explicitly select Arial for a preview. Fonts are not embedded. Visual review in the intended reader remains part of delivery.
