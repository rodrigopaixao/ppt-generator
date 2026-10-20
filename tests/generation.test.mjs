import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { build } from '../src/responsive.mjs';
import { contents } from '../src/content.mjs';

test('seven templates rebuild on a different grid and larger 16:9 canvas with element overrides', async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'pptx-components-test-'));
  try {
    const { manifest, outputPath } = await build({
      slide: { width: 16, height: 9 }, grid: { columns: 12, rows: 8 },
      theme: { fonts: { body: 'Arial', heading: 'Arial' } },
      elements: {
        '50.pillars.items.0.title': { text: 'Configurable priority', fontSize: 17 },
        '68.dashboard.pillars.0.chart': { series: {
          labels: ['Complete', 'In Progress', 'Not Started', 'Extra'], values: [4, 5, 6, 15],
        } },
      },
      slides: { 50: { data: { pillars: [...contents[50].pillars,
        { title: 'Additional priority', icon: contents[50].pillars[0].icon }] } } },
    }, { output: path.join(directory, 'responsive.pptx'), showHidden: true });
    assert(fs.statSync(outputPath).size > 10000);
    assert.equal(manifest.length, 7);
    const pillars = manifest.find(s => s.sourceNumber === 50);
    const titles = pillars.elements.filter(e => /^pillars\.items\.\d+\.title$/.test(e.id));
    assert.equal(titles.length, 5);
    assert.equal(titles[0].text, 'Configurable priority');
    assert.equal(titles[0].fontSize, 17);
    assert(titles[4].box.y > titles[0].box.y, 'fifth item flows onto a new row');
    assert(manifest.every(s => !s.hidden));
    const dashboard = manifest.find(s => s.sourceNumber === 68);
    assert.equal(dashboard.elements.find(e => e.id === 'dashboard.pillars.0.chart.values').text,
      '4   /   5   /   6');
  } finally { fs.rmSync(directory, { recursive: true, force: true }); }
});
