"""Regression coverage for the screenshot-reported layout and icon defects."""
import copy
import json
import sys
import unittest
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from native_deck import ROOT,NS,q,parse_xml,scene_nodes,ancestors_for,box_for,relationships
from layout_constraints import inset_container_text,anchor_table_bars,prepare_slide_layout
from quality_deck import normalize_body,paragraph_text,measure_rich_lines
from picture_compat import repair_svg_pictures


class ReviewRegressionTest(unittest.TestCase):
    """Validate geometry and package relationships independently of screenshots."""

    @classmethod
    def setUpClass(cls):
        """Load immutable source bytes shared across tests."""
        with zipfile.ZipFile(ROOT/'2606 Context Enriched Slide Repository.pptx') as archive:
            cls.parts={name:archive.read(name) for name in archive.namelist()}
        cls.dimensions={'width':13.333333,'height':7.5}

    def test_filled_arrow_is_not_shrunk_inside_another_background(self):
        """The first theme arrow retains the same geometry as its peer arrows."""
        root=parse_xml(self.parts['ppt/slides/slide17.xml']);scene=scene_nodes(root)
        before=box_for(scene['e94']['effectiveTransform'],scene['e94']['parentMatrix'])
        changes=inset_container_text(scene,self.dimensions,.12,.06)
        after_scene=scene_nodes(root)
        after=box_for(after_scene['e94']['effectiveTransform'],after_scene['e94']['parentMatrix'])
        self.assertEqual(before,after)
        self.assertTrue(any(c['id']=='e94' and c['constraint']=='native-container-padding' for c in changes))

    def test_soft_break_contributes_an_actual_line(self):
        """A soft break cannot disappear when estimating text height or rich text."""
        body=parse_xml(f'<p:txBody xmlns:p="{NS["p"]}" xmlns:a="{NS["a"]}"><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>Title</a:t></a:r><a:br/><a:r><a:t>Description</a:t></a:r></a:p></p:txBody>'.encode())
        self.assertEqual(paragraph_text(body.find('a:p',NS)),'Title\nDescription')
        self.assertEqual(measure_rich_lines(body.find('a:p',NS),5,10),2)
        measurement=normalize_body(body,'Arial',10,'dense',1,5,0)
        self.assertGreaterEqual(measurement['requiredHeight'],2*10/72*1.1-.001)

    def test_png_fallback_keeps_svg_and_geometry(self):
        """SVG-only source icons acquire a standard image relation without losing SVG."""
        parts=dict(self.parts)
        fallbacks={name:str(ROOT/'assets/image300.png') for name in parts if name.startswith('ppt/media/') and name.endswith('.svg')}
        repairs=repair_svg_pictures(parts,fallbacks)
        self.assertTrue(any(r['owner']=='ppt/slides/slide52.xml' for r in repairs))
        owner='ppt/slides/slide52.xml';root=parse_xml(parts[owner]);rels=relationships(parts,owner)
        picture=next(p for p in root.findall('.//p:pic',NS) if p.find('p:nvPicPr/p:cNvPr',NS).get('id')=='234')
        blip=picture.find('p:blipFill/a:blip',NS)
        self.assertIn(rels[blip.get(q('r','embed'))]['target'],parts)
        self.assertIsNotNone(blip.find('.//{http://schemas.microsoft.com/office/drawing/2016/SVG/main}svgBlip'))
        self.assertEqual(repair_svg_pictures(parts,fallbacks),[])

    def test_timeline_bar_uses_final_row_center(self):
        """Changing row height moves its bar while retaining its horizontal timing."""
        table=parse_xml(f'<p:graphicFrame xmlns:p="{NS["p"]}" xmlns:a="{NS["a"]}"><a:graphic><a:graphicData><a:tbl><a:tblGrid><a:gridCol w="4572000"/><a:gridCol w="6400800"/></a:tblGrid><a:tr h="457200"/><a:tr h="914400"/></a:tbl></a:graphicData></a:graphic></p:graphicFrame>'.encode())
        # Reuse valid source records for transforms; replace only their native node.
        root=parse_xml(self.parts['ppt/slides/slide23.xml']);scene=scene_nodes(root)
        record=copy.copy(scene['e57']);record['node']=table
        target=scene['e17'];target['name']='custom.bar'
        before=box_for(target['effectiveTransform'],target['parentMatrix'])
        result=anchor_table_bars(scene,record,{'column':1,'items':[{'name':'custom.bar','row':1}]},self.dimensions)
        self.assertAlmostEqual(result[0]['box']['y']+result[0]['box']['h']/2,result[0]['rowCenter'])
        self.assertEqual(result[0]['box']['h'],before['h'])

    def test_theme_title_and_description_keep_separate_hierarchy(self):
        """Theme arrows retain a component heading followed by dense body text."""
        config=json.loads((ROOT/'config.quality.json').read_text())['quality']
        config['flow']['regions']['17']=json.loads((ROOT/'data/layout-review.json').read_text())['regions']['17']
        root=parse_xml(self.parts['ppt/slides/slide17.xml'])
        plan=prepare_slide_layout(root,self.parts,'ppt/slides/slide17.xml',config,self.dimensions)
        record=scene_nodes(root)['e94']
        self.assertEqual(len(record['node'].findall('p:txBody/a:p',NS)),2)
        self.assertEqual(plan['paragraphSizes']['e94'],[12,10])
