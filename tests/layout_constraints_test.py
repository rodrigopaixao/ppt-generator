"""Regressões das faixas, ícones ligados e área exclusiva do rodapé."""
import json
import sys
import unittest
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from native_deck import ROOT, NS, q, parse_xml, scene_nodes, ancestors_for, box_for
from layout_constraints import prepare_slide_layout, text_width, typography
from quality_deck import METRICS, measure_lines, normalize_body


class LayoutConstraintsTest(unittest.TestCase):
    """Mede a geometria real da referência, sem depender apenas de screenshots."""

    @classmethod
    def setUpClass(cls):
        """Carrega o pacote original e os tokens da configuração pública uma vez."""
        with zipfile.ZipFile(ROOT/'2606 Context Enriched Slide Repository.pptx') as archive:
            cls.parts = {n:archive.read(n) for n in archive.namelist()}
        cls.config = json.loads((ROOT/'config.quality.json').read_text())['quality']
        cls.dimensions = {'width':13.333333,'height':7.5}

    def test_tracking_changes_measurement_and_header_background_contains_text(self):
        """INDUSTRY OVERVIEW permanece dentro da faixa com tracking e padding."""
        self.assertGreater(measure_lines('INDUSTRY OVERVIEW',1.7,10,True,2),measure_lines('INDUSTRY OVERVIEW',1.7,10,True,0))
        part = 'ppt/slides/slide38.xml'
        root = parse_xml(self.parts[part])
        plan = prepare_slide_layout(root,self.parts,part,self.config,self.dimensions)
        scene = scene_nodes(root,ancestors_for(self.parts,part))
        previous = None
        for ident in ['e10','e14']:
            r = scene[ident]
            box = box_for(r['effectiveTransform'],r['parentMatrix'])
            _,bold,tracking = typography(r['node'],10)
            text = ''.join(n.text or '' for n in r['node'].iter(q('a','t')))
            self.assertLessEqual(text_width(text,10,bold,tracking,METRICS)+2*self.config['flow']['boxPadding'],box['w']+0.001)
            if previous:
                self.assertGreaterEqual(box['x'],previous['x']+previous['w']-0.001)
            previous = box
        table = scene['e9']
        box = box_for(table['effectiveTransform'],table['parentMatrix'])
        self.assertLessEqual(box['y']+box['h'],plan['contentBottom']+0.001)
        self.assertGreaterEqual(plan['footerTop']-plan['contentBottom'],self.config['flow']['footer']['gap']-0.001)

    def test_locked_font_keeps_icon_gutter_and_rows_flow_without_collision(self):
        """Fixar a fonte não apaga a faixa do ícone; as cinco linhas não colidem."""
        part = 'ppt/slides/slide45.xml'
        root = parse_xml(self.parts[part])
        plan = prepare_slide_layout(root,self.parts,part,self.config,self.dimensions)
        scene = scene_nodes(root,ancestors_for(self.parts,part))
        rows = [box_for(scene[i]['effectiveTransform'],scene[i]['parentMatrix']) for i in ['e8','e9','e10','e11','e270']]
        for first,second in zip(rows,rows[1:]):
            self.assertLessEqual(first['y']+first['h']+self.config['spacing']['gap'],second['y']+0.001)
        self.assertLessEqual(rows[-1]['y']+rows[-1]['h'],plan['contentBottom']+0.001)
        body = scene['e8']['node'].find('p:txBody',NS)
        gutter = body.find('a:bodyPr',NS).get('lIns')
        normalize_body(body,'Arial',12,'dense',rows[0]['h'],rows[0]['w'],0,True,preserve_layout=True)
        self.assertEqual(body.find('a:bodyPr',NS).get('lIns'),gutter)

    def test_longer_card_expands_and_displaces_the_next_row(self):
        """Uma edição longa aumenta o fundo e move a próxima unidade com seus ícones."""
        part = 'ppt/slides/slide45.xml'
        root = parse_xml(self.parts[part])
        scene = scene_nodes(root,ancestors_for(self.parts,part))
        old = box_for(scene['e8']['effectiveTransform'],scene['e8']['parentMatrix'])
        text = scene['e8']['node'].find('p:txBody/a:p/a:r/a:t',NS)
        text.text = 'Engagement Channel with consistent client advice and expanded digital capabilities'
        plan = prepare_slide_layout(root,self.parts,part,self.config,self.dimensions)
        scene = scene_nodes(root,ancestors_for(self.parts,part))
        first = box_for(scene['e8']['effectiveTransform'],scene['e8']['parentMatrix'])
        second = box_for(scene['e9']['effectiveTransform'],scene['e9']['parentMatrix'])
        self.assertGreater(first['h'],old['h'])
        self.assertLessEqual(first['y']+first['h']+self.config['spacing']['gap'],second['y']+0.001)
        last = box_for(scene['e270']['effectiveTransform'],scene['e270']['parentMatrix'])
        self.assertLessEqual(last['y']+last['h'],plan['contentBottom']+0.001)
