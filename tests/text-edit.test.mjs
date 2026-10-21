import test from 'node:test';
import assert from 'node:assert/strict';
import { editRichText } from '../src/text-edit.mjs';

test('text overrides preserve unchanged rich runs and Unicode characters', () => {
  const source = [
    { text: 'Bold ', options: { bold: true, color: '123456' } },
    { text: 'link 😀', options: { hyperlink: { url: 'https://example.com' }, italic: true } },
  ];
  const original = structuredClone(source);
  const edited = editRichText(source, 'New Bold link 😀');
  assert.equal(edited.map(run => run.text).join(''), 'New Bold link 😀');
  assert.deepEqual(edited.at(-1).options, source[1].options);
  assert.deepEqual(edited[0].options, source[0].options);
  assert.deepEqual(source, original);
  assert.equal(editRichText('Original', ''), '');
  assert.deepEqual(editRichText(source, []), []);
});
