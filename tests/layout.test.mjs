import test from 'node:test';
import assert from 'node:assert/strict';
import { Grid, split, wrap } from '../src/layout.mjs';
import { configure } from '../src/theme.mjs';
import { Canvas, fitText, textHeight } from '../src/components.mjs';
import { regions } from '../src/templates.mjs';

test('14 × 9 fills the available area and flows in reading order', () => {
  const box = { x: 0.5, y: 0.3, w: 12, h: 6.9 };
  const grid = new Grid(box);
  assert.deepEqual(grid.cell(0, 0, 14, 9), box);
  const items = grid.flow([{ colSpan: 8 }, { colSpan: 6 }, { colSpan: 7 }, { colSpan: 7 }]);
  assert.equal(items[0].box.y, items[1].box.y);
  assert(items[1].box.x > items[0].box.x);
  assert(items[2].box.y > items[1].box.y);
  assert.equal(items[2].box.y, items[3].box.y);
  assert.throws(() => grid.cell(13, 0, 2));
});

test('responsive collections reflow when available width decreases', () => {
  const wide = wrap({ x: 0, y: 0, w: 12, h: 5 }, 4, { minWidth: 2.5, gap: 0.2 });
  const narrow = wrap({ x: 0, y: 0, w: 6, h: 5 }, 4, { minWidth: 2.5, gap: 0.2 });
  assert(wide.every(b => b.y === 0));
  assert.equal(narrow[0].y, narrow[1].y);
  assert(narrow[2].y > narrow[1].y);
  for (const b of narrow) assert(b.x + b.w <= 6.001 && b.y + b.h <= 5.001);
});

test('grid configuration changes regions and 16:9 remains enforced', () => {
  const a = regions(configure());
  const b = regions(configure({ grid: { columns: 12, rows: 8 } }));
  assert.notEqual(a.body.h, b.body.h);
  assert.equal(b.grid.columns, 12);
  assert.throws(() => configure({ slide: { width: 10, height: 7.5 } }), /16:9/);
  assert.throws(() => new Grid({ x: 0, y: 0, w: 1, h: 1 }, { columns: 14, gapX: 1 }));
});

test('font fitting either fits without truncation or reports an impossible layout', () => {
  const value = 'A configurable component preserves every word. '.repeat(5);
  const box = { x: 0, y: 0, w: 3, h: 1 };
  const size = fitText(value, box, { fontSize: 15, minFontSize: 6 });
  assert(size < 15);
  assert(textHeight(value, box.w, size) <= box.h + 0.01);
  assert.throws(() => fitText(value, { w: 0.1, h: 0.1 }, { minFontSize: 10 }));
});

test('weighted flows fill exactly and nested config overrides preserve other tokens', () => {
  const boxes = split({ x: 0, y: 0, w: 10, h: 5 }, [1, 2, 1], 'x', 0.2);
  assert(Math.abs(boxes.at(-1).x + boxes.at(-1).w - 10) < 1e-8);
  const config = configure({ theme: { colors: { primary: '112233' } } });
  assert.equal(config.theme.colors.primary, '112233');
  assert.equal(config.theme.colors.surface, 'F5EFE8');
});

test('component configuration wins over local defaults and element overrides win last', () => {
  const config = configure({ components: { text: { fontSize: 18, color: '111111' } },
    elements: { '5.title': { color: '222222' } } });
  const canvas = new Canvas(null, null, config, 5, {}, []);
  const options = canvas.options('text', 'title', { fontSize: 10, color: '000000' });
  assert.equal(options.fontSize, 18);
  assert.equal(options.color, '222222');
});
