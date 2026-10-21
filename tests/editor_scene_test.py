import sys
from pathlib import Path
import unittest
import tempfile
import zipfile
import json
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import editor_scene
from editor_text import edit_body, body_text, text_body
import native_deck as native


class EditorSceneTest(unittest.TestCase):
    def test_build_catalog_can_be_read_without_writing_shared_data(self):
        with patch.object(native, 'write_json_atomic', side_effect=AssertionError('Unexpected catalog write')):
            catalog = native.source_catalog(native.SOURCE, output=None)
        self.assertEqual(catalog['counts']['slides'], 71)

    def record(self, text_xml):
        node = ET.fromstring(f'<p:sp xmlns:p="{native.NS["p"]}" xmlns:a="{native.NS["a"]}"><p:txBody><a:bodyPr/><a:lstStyle/>{text_xml}</p:txBody></p:sp>')
        return node, {'hidden': False, 'effectiveTransform': ET.fromstring('<xfrm/>'),
                      'parentMatrix': (1, 0, 0, 1, 0, 0)}

    def test_plain_multiline_and_unicode_are_editable(self):
        node, record = self.record('<a:p><a:r><a:t>Hello 😀</a:t></a:r></a:p><a:p><a:r><a:t>Second line</a:t></a:r></a:p>')
        self.assertTrue(editor_scene.simple_text(node, record))

    def test_mixed_style_fields_and_bullets_are_editable(self):
        cases = [
            '<a:p><a:r><a:rPr b="1"/><a:t>Bold</a:t></a:r><a:r><a:t>Plain</a:t></a:r></a:p>',
            '<a:p><a:fld id="1"><a:t>1</a:t></a:fld></a:p>',
            '<a:p><a:pPr><a:buChar char="•"/></a:pPr><a:r><a:t>Item</a:t></a:r></a:p>',
        ]
        for value in cases:
            node, record = self.record(value)
            self.assertTrue(editor_scene.simple_text(node, record))

    def test_source_scene_maps_to_patchable_ids(self):
        scenes = editor_scene.scenes(native.SOURCE, 'fidelity')
        self.assertEqual(len(scenes), 71)
        summary = next(s for s in scenes if s['number'] == 5)
        heading = next(e for e in summary['elements'] if e['id'] == 'e5')
        self.assertTrue(heading['editable'])
        self.assertEqual(heading['role'], 'title')
        self.assertEqual(heading['style']['fontSize'], 22)
        body = next(e for e in summary['elements'] if e['id'] == 'e9')
        self.assertTrue(body['editable'])

    def test_rich_edit_preserves_bullets_hyperlinks_fields_and_run_styles(self):
        node, _ = self.record('<a:p><a:pPr><a:buChar char="•"/></a:pPr><a:r><a:rPr b="1"/><a:t>Bold</a:t></a:r><a:r><a:rPr i="1"><a:hlinkClick/></a:rPr><a:t> link</a:t></a:r><a:fld id="slide-number" type="slidenum"><a:rPr sz="900"/><a:t>7</a:t></a:fld></a:p>')
        body = text_body(node)
        edit_body(body, 'Bolder link7')
        self.assertEqual(body_text(body), 'Bolder link7')
        self.assertEqual(body.find('a:p/a:pPr/a:buChar', native.NS).get('char'), '•')
        self.assertIsNotNone(body.find('.//a:hlinkClick', native.NS))
        self.assertEqual(body.find('.//a:fld', native.NS).get('id'), 'slide-number')
        self.assertEqual(body.find('.//a:rPr', native.NS).get('b'), '1')
        edit_body(body, 'Bolder link8')
        self.assertIsNone(body.find('.//a:fld', native.NS))
        self.assertEqual(body_text(body), 'Bolder link8')

    def test_table_cells_export_independently_preserving_component_structure(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source.pptx'
            output = Path(folder) / 'edited.pptx'
            presentation = f'<p:presentation xmlns:p="{native.NS["p"]}" xmlns:r="{native.NS["r"]}"><p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst><p:sldSz cx="9144000" cy="5143500"/></p:presentation>'
            slide = f'<p:sld xmlns:p="{native.NS["p"]}" xmlns:a="{native.NS["a"]}"><p:cSld><p:spTree><p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="8" name="Data table"/></p:nvGraphicFramePr><p:xfrm><a:off x="914400" y="914400"/><a:ext cx="3657600" cy="1828800"/></p:xfrm><a:graphic><a:graphicData><a:tbl><a:tblPr/><a:tblGrid><a:gridCol w="1828800"/><a:gridCol w="1828800"/></a:tblGrid><a:tr h="914400"><a:tc gridSpan="2"><a:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr b="1"/><a:t>Merged header</a:t></a:r></a:p></a:txBody><a:tcPr marL="91440"><a:solidFill><a:srgbClr val="123456"/></a:solidFill></a:tcPr></a:tc><a:tc hMerge="1"><a:txBody><a:bodyPr/><a:p/></a:txBody><a:tcPr/></a:tc></a:tr><a:tr h="914400"><a:tc><a:txBody><a:bodyPr/><a:p><a:r><a:t>Sibling</a:t></a:r></a:p></a:txBody><a:tcPr/></a:tc><a:tc><a:txBody><a:bodyPr/><a:p/></a:txBody><a:tcPr/></a:tc></a:tr></a:tbl></a:graphicData></a:graphic></p:graphicFrame></p:spTree></p:cSld></p:sld>'
            rels = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/></Relationships>'
            with zipfile.ZipFile(source, 'w') as archive:
                archive.writestr('ppt/presentation.xml', presentation)
                archive.writestr('ppt/_rels/presentation.xml.rels', rels)
                archive.writestr('ppt/slides/slide1.xml', slide)
            scene = editor_scene.scenes(source, 'fidelity')[0]
            self.assertEqual(len(scene['elements']), 3)
            header = scene['elements'][0]
            self.assertEqual(header['box'], {'x': 1, 'y': 1, 'w': 4, 'h': 1})
            self.assertTrue(all(e['editable'] for e in scene['elements']))
            self.assertEqual(scene['elements'][-1]['text'], '')
            editor_scene.apply_edits(source, 'fidelity', {'1.e8/cell/0/0': 'Updated header', '1.e8/cell/1/1': 'New <&> 😀\nSecond line'}, output)
            edited = editor_scene.scenes(output, 'fidelity')[0]
            self.assertEqual(edited['elements'][0]['text'], 'Updated header')
            self.assertEqual(edited['elements'][1]['text'], 'Sibling')
            self.assertEqual(edited['elements'][2]['text'], 'New <&> 😀\nSecond line')
            root = native.parse_xml(native.read_parts(output)['ppt/slides/slide1.xml'])
            self.assertEqual(root.find('.//a:tc', native.NS).get('gridSpan'), '2')
            self.assertEqual(root.find('.//a:tcPr/a:solidFill/a:srgbClr', native.NS).get('val'), '123456')
            self.assertEqual(root.find('.//a:rPr', native.NS).get('b'), '1')

    def test_inherited_text_edits_clone_shared_layout_and_master(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'private-layout.pptx'
            scene = editor_scene.scenes(native.SOURCE, 'fidelity')[0]
            inherited = next(e for e in scene['elements'] if e['target']['layer'] != 'slide')
            baseline = native.read_parts(native.SOURCE)
            original_layouts = {name: payload for name, payload in baseline.items() if name.startswith(('ppt/slideLayouts/', 'ppt/slideMasters/'))}
            editor_scene.apply_edits(native.SOURCE, 'fidelity', {'1.' + inherited['id']: 'Private inherited text'}, output)
            result = native.read_parts(output)
            self.assertTrue(all(result[name] == payload for name, payload in original_layouts.items()))
            updated = editor_scene.scenes(output, 'fidelity')[0]
            self.assertEqual(next(e for e in updated['elements'] if e['id'] == inherited['id'])['text'], 'Private inherited text')
            self.assertTrue(any('/editor-slide1-' in name for name in result))
            other_part = 'ppt/slides/slide2.xml'
            self.assertEqual(result[other_part], baseline[other_part])

    def test_local_bullet_suppression_and_field_typography_override_inherited_defaults(self):
        node, _ = self.record('<a:p><a:pPr><a:buNone/></a:pPr><a:fld id="1"><a:rPr sz="1100" b="1"/><a:t>Jun</a:t></a:fld></a:p>')
        body = text_body(node)
        defaults = body.find('a:lstStyle', native.NS)
        level = ET.SubElement(defaults, native.q('a', 'lvl1pPr'))
        ET.SubElement(level, native.q('a', 'buChar'), {'char': '•'})
        theme = {'fonts': {}, 'colors': {}, 'mapping': {}}
        paragraphs = editor_scene.rich_paragraphs(node, [], theme)
        self.assertNotIn('bullet', paragraphs[0])
        self.assertEqual(paragraphs[0]['runs'][0]['style']['fontSize'], 11)
        self.assertEqual(editor_scene.style_for(node, [], None, theme)['fontSize'], 11)


if __name__ == '__main__':
    unittest.main()
