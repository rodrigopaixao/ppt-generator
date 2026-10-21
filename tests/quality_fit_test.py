"""Rules for preferred font sizes and shrinking before layout changes."""
import sys
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from native_deck import NS, q
from quality_deck import fit_body_size


class FontFitTest(unittest.TestCase):
    """Prefer the default size, enforce the minimum and measure without changing text."""

    def test_prefers_standard_then_reduces_only_when_needed(self):
        """A wide box retains 16 pt; a smaller box requires gradual shrinking to fit."""
        body = ET.fromstring(f'<a:txBody xmlns:a="{NS["a"]}"><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>This complete paragraph must fit inside the available area.</a:t></a:r></a:p></a:txBody>')
        before = ET.tostring(body)
        self.assertEqual(fit_body_size(body,'Arial',16,12,'body',2,3,0.025,{}),16)
        smaller = fit_body_size(body,'Arial',16,12,'body',0.45,3,0.025,{})
        self.assertGreaterEqual(smaller,12)
        self.assertLess(smaller,16)
        self.assertEqual(round(smaller*4),smaller*4)
        self.assertEqual(ET.tostring(body),before)

    def test_never_crosses_floor_and_can_disable_fitting(self):
        """Content that cannot fit returns the minimum for reflow; invalid steps fail."""
        body = ET.fromstring(f'<a:txBody xmlns:a="{NS["a"]}"><a:p><a:r><a:t>Long text requiring more room than provided.</a:t></a:r></a:p></a:txBody>')
        self.assertEqual(fit_body_size(body,'Arial',16,12,'body',0.1,1,0,{}),12)
        self.assertEqual(fit_body_size(body,'Arial',16,12,'body',0.1,1,0,{'enabled':False}),16)
        with self.assertRaises(ValueError):
            fit_body_size(body,'Arial',16,12,'body',0.1,1,0,{'step':0.001})
