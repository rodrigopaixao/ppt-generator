"""Regras de preferência e redução de fonte antes de modificar o layout."""
import sys
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from native_deck import NS, q
from quality_deck import fit_body_size


class FontFitTest(unittest.TestCase):
    """O padrão é prioritário, o piso é obrigatório e a medição não modifica texto."""

    def test_prefers_standard_then_reduces_only_when_needed(self):
        """Uma caixa ampla mantém 16pt; uma menor exige redução gradual até caber."""
        body = ET.fromstring(f'<a:txBody xmlns:a="{NS["a"]}"><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>This complete paragraph must fit inside the available area.</a:t></a:r></a:p></a:txBody>')
        before = ET.tostring(body)
        self.assertEqual(fit_body_size(body,'Arial',16,12,'body',2,3,0.025,{}),16)
        smaller = fit_body_size(body,'Arial',16,12,'body',0.45,3,0.025,{})
        self.assertGreaterEqual(smaller,12)
        self.assertLess(smaller,16)
        self.assertEqual(round(smaller*4),smaller*4)
        self.assertEqual(ET.tostring(body),before)

    def test_never_crosses_floor_and_can_disable_fitting(self):
        """Conteúdo impossível retorna o piso para o reflow; step inválido falha."""
        body = ET.fromstring(f'<a:txBody xmlns:a="{NS["a"]}"><a:p><a:r><a:t>Long text requiring more room than provided.</a:t></a:r></a:p></a:txBody>')
        self.assertEqual(fit_body_size(body,'Arial',16,12,'body',0.1,1,0,{}),12)
        self.assertEqual(fit_body_size(body,'Arial',16,12,'body',0.1,1,0,{'enabled':False}),16)
        with self.assertRaises(ValueError):
            fit_body_size(body,'Arial',16,12,'body',0.1,1,0,{'step':0.001})
