# JavaScript API, CLI, and manifests

[Documentation index](README.md)

The project uses ES modules. The examples below assume root-relative imports from a module in the project root or from a root `node --input-type=module` session. Build output paths and source/image overrides resolve from the repository root; CLI configuration filenames are read relative to the invoking working directory.

## Native build API

```js
import fs from 'node:fs';
import { build } from './src/generate.mjs';

const config = JSON.parse(fs.readFileSync('config.quality.json', 'utf8'));
const { outputPath, manifest, report } = await build(config, {
  output: 'output/documented-build.pptx',
  showHidden: true,
});
console.log(outputPath, manifest.length, report.counts.outputSlides);
```

`build(patch={},options={})` returns a promise for `{outputPath,manifest,report}`. Default output: `output/recreated-slides.pptx`. `manifest` is the report's slide array. `showHidden` defaults to false and, when true, sets the effective native configuration to show hidden slides. Input configuration is cloned. Errors propagate; temporary directories are cleaned in `finally` blocks. The output extension must be `.pptx`, and the source cannot be overwritten.

The bare API has no quality profile. Pass `quality:{}` to use all quality defaults or load the checked-in profile for the normal full-deck behavior.

### Other native exports

| Export | Contract |
| --- | --- |
| `nativeCommand(args)` | Runs `scripts/native_deck.py` with an argument array; returns trimmed stdout; throws with diagnostics on failure |
| `validateAdditionBox(box,size)` | Returns the same positive, finite, on-canvas box; throws otherwise |
| `addNativeObjects(slide,additions,config,size)` | Adds supported text/shape/table/chart declarations to a PptxGenJS slide |
| `preparePictureOverrides(config,directory)` | Async; mutates a working config's SVG replacement fields to `{path,fallback}` |
| `parseArguments(args)` | Returns `{mode,patch,options}`; validates flags and reads configuration JSON |

## Responsive API

```js
import { build as buildResponsive } from './src/responsive.mjs';

const result = await buildResponsive({
  theme: { fonts: { body: 'Arial', heading: 'Arial' } },
}, { output: 'output/responsive-api.pptx', showHidden: true });
```

Returns `{pptx,manifest,config,outputPath}`. The default output is `output/responsive-slides.pptx`. `pptx` is the generated PptxGenJS instance; `config` is the validated resolved configuration. The fixed seven-source build list is independent of native `selection`.

`prepareAssets(config)` returns a promise for a map keyed by original asset path, with `{path,width,height}` for each prepared PNG. It writes under `output/assets/`.

## Configuration and template exports

| Module / export | Contract |
| --- | --- |
| `theme.mjs: merge(base,patch={})` | Immutable recursive object merge; arrays replaced as units |
| `theme.mjs: brand`, `defaults` | Responsive token and configuration defaults |
| `theme.mjs: configure(patch={})` | Merge and validate responsive settings |
| `quality.mjs: qualityDefaults` | Native quality token values and source bindings |
| `quality.mjs: prepareQuality(patch,catalog)` | Clone patch, resolve quality settings, produce replacement declarations |
| `templates.mjs: templates` | Map of seven semantic renderer functions |
| `templates.mjs: regions(config)` | `{grid,header,body,footer}` |
| `templates.mjs: registerMasters(pptx,config,assets)` | Register reusable responsive layouts and static artwork |
| `templates.mjs: chrome(canvas,data,regions)` | Draw per-slide header/footer content |
| `templates.mjs: renderTemplate(canvas,data)` | Merge template settings, draw chrome, dispatch body renderer |
| `content.mjs: source`, `contents` | Extracted source slides and seven semantic content entries |
| `dependencies.mjs: dependency(name)` | Resolve local CommonJS dependency, with optional runtime fallback |

Geometry and drawing exports are documented in [Components](components.md).

## CLI flags

```sh
node src/generate.mjs [options]
```

| Flag | Value / default | Notes |
| --- | --- | --- |
| `--mode` | `fidelity` or `responsive`; default fidelity | Overrides config `mode`; no `quality` mode value |
| `--config` | JSON filename | Read before CLI overrides |
| `--output` | PPTX path | Mode-specific default filename |
| `--font` | Font family | Sets both theme body and heading fonts; quality normalization also has its own `quality.font` |
| `--grid` | `14x9` or `14:9` | Sets column/row counts; not slide aspect ratio |
| `--slides` | `5,10,50` | Native source selection; responsive loop does not consume it |
| `--show-hidden` | Flag | Exposes hidden slides |
| `--debug` | Flag | Responsive only; enables grid and text outlines |

Unknown flags and missing values throw. The parser does not implement a `--help` flag. CLI overrides apply after loading JSON. For quality font changes, set `quality.font` in configuration; `--font` alone does not override the later normalizer's family.

## npm commands

| Command | Entry point / purpose |
| --- | --- |
| `npm run extract` | `native_deck.py catalog` |
| `npm run extract:responsive` | `extract.py` |
| `npm run build` | Native CLI with `config.quality.json` |
| `npm run build:fidelity` | Bare native CLI |
| `npm run build:quality` | Quality CLI writing `output/reviewed-slides.pptx` |
| `npm run build:responsive` | Responsive CLI |
| `npm run build:debug` | Responsive CLI with debug |
| `npm test` | Node tests, then Python unittest discovery |
| `npm run docs:check` | Inline JSDoc/docstring presence audit |
| `npm run verify` | Structural verification of default output |
| `npm run verify:visual` | Baseline pixel comparison with reference |
| `npm run verify:quality` | LibreOffice rendering and quality contact sheets |
| `npm run verify:keynote` | Keynote import count, PDF, and hash audit |

`verify:visual` is intended for an unchanged fidelity baseline. Quality intentionally changes layout and can add pages, so baseline pixel equality is not its acceptance criterion.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `PYTHON` | Python executable used by JavaScript's native adapter; defaults to `python3` |
| `CODEX_NODE_MODULES` | Optional directory used by dependency resolution after local modules cannot be found |
| `PATH` | Locates Python and optional renderer executables |

The Python commands in npm scripts invoke `python3` directly; `PYTHON` only affects JavaScript's adapter invocation.

## Output manifests

### Native `.layout.json`

| Field | Meaning |
| --- | --- |
| `mode` | `fidelity`, including quality-profile builds |
| `sourceFile`, `sourceSha256`, `outputSha256` | Provenance and exact artifact identity |
| `slideSize`, `grid`, `selection` | Dimensions, grid settings, original selection/order |
| `counts` | Catalog counts plus output slides and imported additions |
| `changedParts`, `unchangedSourceParts` | Package-level change audit |
| `baselineVisualPartsByteIdentical` | True only when all source visual/binary parts remain byte-identical; excludes core metadata |
| `fonts` | Font preservation/materialization explanation |
| `scaffold` | PptxGenJS provenance and scaffold slide count |
| `slides` | Ordered source number, OPC part, and actual element descriptors; includes continuation entries |
| `quality` | Resolved tokens, measurements, overflow, layout constraints, continuations, and workbook repairs when enabled |

A source number can appear more than once because of continuations. Use ordered array position for output page and `part` for the actual OPC slide. Element descriptors retain native hierarchy and resolved geometry; additions can have generated numeric IDs as well as semantic names.

### Responsive `.layout.json`

Contains `slideSize`, `grid`, `fontMetrics`, `theme`, and `slides`. Each slide has `sourceNumber`, `template`, `hidden`, and `elements`. Text records include `fontSize` and `estimatedHeight`; tables include row heights and counts; charts include effective series. This manifest is geometry-oriented and has no native package byte-preservation claim.

### Python adapter CLI

```sh
python3 scripts/native_deck.py catalog --source '2606 Context Enriched Slide Repository.pptx' --catalog-output /tmp/deck-catalog.json
```

The adapter also supports `build --source ... --scaffold ... --config ... --output ...`; prefer the JavaScript API, which creates and validates the matching scaffold. Direct calls are primarily for internal maintenance and debugging.
