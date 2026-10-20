"""Testes de invariantes do adaptador: edição nativa, isolamento e sincronização."""
import copy
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'scripts'))
from native_deck import (SOURCE, NS, EMU, read_parts, parse_xml, scene_nodes,
    ancestors_for, apply_element, patch_chart, relationships, text_of, patch_part,
    validate_config, xml_bytes, source_catalog, workbook_cells)


class NativeDeckTests(unittest.TestCase):
    """Carrega a referência uma vez; cada teste usa seu próprio mapa de partes."""

    @classmethod
    def setUpClass(cls):
        """Retém bytes imutáveis da referência para não compartilhar mutações XML."""
        cls.original = read_parts(SOURCE)
        cls.size = {'width': 13.333333333333334, 'height': 7.5}

    def setUp(self):
        """Cria um mapa novo; os bytes compartilhados são imutáveis em Python."""
        self.parts = dict(self.original)

    def test_text_override_keeps_unrelated_parts(self):
        """Mudar título e fonte altera somente o slide e preserva o layout herdado."""
        part = 'ppt/slides/slide5.xml'
        patch_part(self.parts, part, {'elements': {'e5': {'text': 'Novo resumo',
            'textStyle': {'fontSize': 19, 'color': 'EC111A'}}}}, {}, self.size, 's5')
        self.assertIn('Novo resumo', text_of(parse_xml(self.parts[part])))
        self.assertEqual([p for p in self.parts if self.parts[p] != self.original[p]], [part])

    def test_cell_override_retains_native_table(self):
        """Uma célula muda sem converter a tabela em retângulos ou imagens."""
        part = 'ppt/slides/slide10.xml'
        patch_part(self.parts, part, {'elements': {'e8': {'table': {'cells': {
            '1.2': {'text': 'Transfer atualizado', 'fill': 'F5EFE8'}}}}}}, {}, self.size, 's10')
        root = parse_xml(self.parts[part])
        self.assertEqual(len(root.findall('.//a:tbl', NS)), 1)
        self.assertIn('Transfer atualizado', text_of(root))

    def test_chart_cache_and_embedded_workbook_are_synchronized(self):
        """Clonar/editar um gráfico atualiza valores no XML e no XLSX privado."""
        part = 'ppt/slides/slide68.xml'
        root = parse_xml(self.parts[part])
        node = scene_nodes(root, ancestors_for(self.parts, part))['e114']['node']
        old_chart = self.parts['ppt/charts/chart24.xml']
        patch_chart(self.parts, part, node, {'series': [{'values': [2, 7, 2, 11]}]}, 'test-chart')
        chart = parse_xml(self.parts['ppt/charts/config-test-chart.xml'])
        values = [float(v.text) for v in chart.findall('.//c:ser/c:val//c:pt/c:v', NS)]
        self.assertEqual(values, [2, 7, 2, 11])
        self.assertEqual(self.parts['ppt/charts/chart24.xml'], old_chart)
        workbook = next(r['target'] for r in relationships(self.parts,
            'ppt/charts/config-test-chart.xml').values() if r['target'].endswith('.xlsx'))
        with zipfile.ZipFile(io.BytesIO(self.parts[workbook])) as archive:
            sheet = parse_xml(archive.read('xl/worksheets/sheet1.xml'))
            self.assertEqual(sheet.find('.//s:c[@r="B2"]/s:v', NS).text, '2')
            self.assertEqual(sheet.find('.//s:c[@r="B3"]/s:v', NS).text, '7')

    def test_placeholder_geometry_materializes_and_grid_is_configurable(self):
        """Um título herdado recebe geometria própria ao ser movido pelo grid."""
        part = 'ppt/slides/slide5.xml'
        patch_part(self.parts, part, {'elements': {'e5': {'grid': {
            'col': 1, 'row': 1, 'colSpan': 10, 'rowSpan': 1}}}},
            {'grid': {'columns': 12, 'rows': 8}}, self.size, 's5')
        record = scene_nodes(parse_xml(self.parts[part]))['e5']
        xf = record['effectiveTransform']
        self.assertAlmostEqual(int(xf.find('a:off', NS).get('x'))/EMU, self.size['width']/12, places=5)

    def test_group_resize_preserves_all_child_xml(self):
        """Redimensionar o grupo altera xfrm do pai, mantendo cada objeto filho."""
        part = 'ppt/slides/slide50.xml'
        before = scene_nodes(parse_xml(self.parts[part]))
        child = xml_bytes(before['e27']['node'])
        patch_part(self.parts, part, {'elements': {'e4': {'box': {
            'x': 1, 'y': 2, 'w': 10, 'h': 4}}}}, {}, self.size, 's50')
        after = scene_nodes(parse_xml(self.parts[part]))
        self.assertEqual(xml_bytes(after['e27']['node']), child)
        self.assertEqual(len(before), len(after))

    def test_flow_fills_rows_in_reading_order(self):
        """Quatro textos em região estreita passam a duas linhas, sem perda de palavras."""
        part = 'ppt/slides/slide50.xml'
        ids = ['e25', 'e26', 'e27', 'e28']
        patch_part(self.parts, part, {'flows': [{'elements': ids, 'minWidth': 2,
            'region': {'x': 1, 'y': 2, 'w': 5, 'h': 4}, 'gap': 0.1}]}, {}, self.size, 's50')
        scene = scene_nodes(parse_xml(self.parts[part]))
        from native_deck import box_for
        boxes = [box_for(scene[k]['effectiveTransform'], scene[k]['parentMatrix']) for k in ids]
        self.assertAlmostEqual(boxes[0]['y'], boxes[1]['y'], places=5)
        self.assertGreater(boxes[1]['x'], boxes[0]['x'])
        self.assertGreater(boxes[2]['y'], boxes[1]['y'])

    def test_unknown_configuration_is_rejected(self):
        """Erros de digitação falham em vez de produzirem um deck aparentemente configurado."""
        with self.assertRaises(ValueError):
            validate_config({'components': {}})
        with self.assertRaises(ValueError):
            patch_part(self.parts, 'ppt/slides/slide5.xml', {'elements': {'e99999': {'text': 'x'}}}, {}, self.size, 's5')

    def test_compatibility_prefixes_survive_xml_changes(self):
        """Prefixos citados por mc:Ignorable continuam declarados após serialização."""
        payload = b'<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main" mc:Ignorable="p14"/>'
        output = xml_bytes(parse_xml(payload))
        self.assertIn(b'xmlns:p14=', output)
        parse_xml(output)

    def test_opc_control_parts_keep_their_default_namespace(self):
        """Content Types e Relationships mantêm nomes lexicais aceitos por leitores OPC."""
        for part, root_name in [('[Content_Types].xml', 'Types'),
                                ('ppt/slides/_rels/slide68.xml.rels', 'Relationships')]:
            value = xml_bytes(parse_xml(self.parts[part]))
            self.assertIn(('<'+root_name+' xmlns=').encode(), value)


if __name__ == '__main__':
    unittest.main()
