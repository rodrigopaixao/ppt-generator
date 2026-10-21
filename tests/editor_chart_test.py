"""Integration coverage for measured chart labels and native data preservation."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import editor_chart
import editor_scene
import native_deck as native


@unittest.skipUnless(shutil.which('soffice') and importlib.util.find_spec('pdfplumber'),
                     'Chart text integration requires LibreOffice and pdfplumber')
class EditorChartTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='chart-editor-test-')
        cls.folder = Path(cls.directory.name)
        cls.source = cls.folder / 'source.pptx'
        subprocess.run(['node', str(ROOT / 'tests/fixtures/chart-text.mjs'), str(cls.source)], check=True, capture_output=True)
        parts = native.read_parts(cls.source)
        # Both slides deliberately share a chart/workbook. Editing slide 1 must
        # leave slide 2's relationship and original chart bytes untouched.
        first = next(r['target'] for r in native.relationships(parts, 'ppt/slides/slide1.xml').values() if r['type'].endswith('/chart'))
        rel_path = native.rel_path('ppt/slides/slide2.xml')
        rels = native.parse_xml(parts[rel_path])
        for relation in rels:
            if relation.get('Type').endswith('/chart'):
                relation.set('Target', '../charts/' + Path(first).name)
        parts[rel_path] = native.xml_bytes(rels)
        editor_chart.write_package(parts, cls.source)
        cls.scene = editor_scene.scenes(cls.source, 'fidelity')[0]
        cls.elements = editor_chart.extract(cls.source, cls.scene)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_rendered_labels_include_titles_legend_categories_values_and_rotated_axes(self):
        labels = {element['text'] for element in self.elements}
        self.assertTrue({'Quarterly revenue', 'Northern region', 'Southern region', 'Jan', 'Month', 'Revenue', '25'} <= labels)
        rotated = next(element for element in self.elements if element['text'] == 'Revenue')
        self.assertEqual(rotated['rotation'], -90)
        self.assertAlmostEqual(rotated['style']['fontSize'], 10, delta=0.1)
        self.assertTrue(all(element['editable'] and element['target']['kind'] == 'chartText' for element in self.elements))
        self.assertEqual(len({element['id'] for element in self.elements}), len(self.elements))

    def test_literal_label_edits_isolate_chart_and_preserve_series_workbooks_and_siblings(self):
        import pdfplumber
        output = self.folder / 'edited.pptx'
        selected = {text: next(element for element in self.elements if element['text'] == text)
                    for text in ('Quarterly revenue', 'Northern region', '25')}
        edits = {f'1.{selected["Quarterly revenue"]["id"]}': 'Edited revenue <&>',
                 f'1.{selected["Northern region"]["id"]}': 'Updated region',
                 f'1.{selected["25"]["id"]}': 'Custom value'}
        editor_scene.apply_edits(self.source, 'fidelity', edits, output, [{'number': 1, 'elements': self.elements}])
        before, after = native.read_parts(self.source), native.read_parts(output)
        for name, payload in before.items():
            if name.startswith(('ppt/charts/', 'ppt/embeddings/')) or name.startswith('ppt/slides/slide2'):
                self.assertEqual(after[name], payload, name)
        self.assertEqual(after[native.rel_path('ppt/slides/slide2.xml')], before[native.rel_path('ppt/slides/slide2.xml')])
        frame = editor_chart.chart_frames(after, self.scene)[0]
        original_frame = editor_chart.chart_frames(before, self.scene)[0]
        self.assertNotEqual(frame['chartPart'], original_frame['chartPart'])
        original = native.parse_xml(before[original_frame['chartPart']])
        edited = native.parse_xml(after[frame['chartPart']])
        self.assertEqual([node.text for node in original.findall('.//c:ser//c:v', native.NS)],
                         [node.text for node in edited.findall('.//c:ser//c:v', native.NS)])
        scene = editor_scene.scenes(output, 'fidelity')[0]
        for key, text in edits.items():
            self.assertEqual(next(e for e in scene['elements'] if e['id'] == key.removeprefix('1.'))['text'], text)
        render = self.folder / 'edited-render'
        render.mkdir(exist_ok=True)
        pdf = editor_chart.render_pdf(after, self.scene, render)
        with pdfplumber.open(pdf) as document:
            words = editor_chart.rendered_words(document.pages[0])
            texts = [word['text'] for word in words]
        self.assertIn('Edited revenue <&>', texts)
        self.assertIn('Updated region', texts)
        self.assertIn('Custom value', texts)
        self.assertIn('Revenue', texts)
        self.assertEqual(texts.count('Southern region'), 1)
        self.assertNotIn('Northern region', texts)

    def test_projected_labels_follow_the_chart_without_mutating_baseline(self):
        original = self.elements[0]
        before = dict(original['box'])
        frame = {'box': dict(original['target']['chartBox'])}
        frame['box'].update(x=frame['box']['x']+1, y=frame['box']['y']+2,
                            w=frame['box']['w']*2, h=frame['box']['h']*2)
        result = editor_chart.project_element(original, frame)
        self.assertAlmostEqual(result['box']['w'], before['w']*2)
        self.assertAlmostEqual(result['box']['h'], before['h']*2)
        self.assertAlmostEqual(result['style']['fontSize'], original['style']['fontSize']*2)
        self.assertEqual(original['box'], before)
        self.assertEqual(result['id'], original['id'])

    def test_muting_chart_glyphs_preserves_plot_structure(self):
        chart = ET.fromstring(f'<c:chartSpace xmlns:c="{native.NS["c"]}" xmlns:a="{native.NS["a"]}"><c:chart><c:plotArea><c:barChart><c:ser><c:tx><c:v>Sales</c:v></c:tx></c:ser></c:barChart></c:plotArea></c:chart></c:chartSpace>')
        editor_chart.transparent_text(chart)
        self.assertEqual(chart.find('.//c:ser/c:tx/c:v', native.NS).text, 'Sales')
        self.assertIsNotNone(chart.find('.//c:barChart', native.NS))
        self.assertEqual(chart.find('c:txPr//a:alpha', native.NS).get('val'), '0')


if __name__ == '__main__':
    unittest.main()
