"""Regression tests for workbooks that caused Keynote/Preview to drop charts."""
import io
import sys
import unittest
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from native_deck import ROOT, NS, q, parse_xml, xml_bytes, rel_path
from chart_compat import S, cached_cells, normalize_chart_workbooks, workbook_bytes


class ChartCompatibilityTest(unittest.TestCase):
    """Ensure valid XLSX ranges and numeric data identical to the original cache."""

    def test_binary_workbook_is_replaced_without_changing_chart_values(self):
        """chart17 remains native with editable XLSX and unchanged values."""
        with zipfile.ZipFile(ROOT/'2606 Context Enriched Slide Repository.pptx') as archive:
            parts={name:archive.read(name) for name in archive.namelist()}
        part='ppt/charts/chart17.xml';before=parts[part]
        expected=cached_cells(parse_xml(before))
        repairs=normalize_chart_workbooks(parts)
        repair=next(item for item in repairs if item['chart']==part)
        self.assertEqual(parts[part],before)
        self.assertEqual(repair['repair'],'cached-xlsx-replaces-xlsb')
        with zipfile.ZipFile(io.BytesIO(parts[repair['workbook']])) as book:
            sheet=parse_xml(book.read('xl/worksheets/sheet1.xml'))
            actual={cell.get('r'):cell.findtext(f'{{{S}}}v') for cell in sheet.findall(f'.//{{{S}}}c') if cell.get('t')=='n'}
        for (_,cells) in expected.items():
            for (row,col),(value,numeric) in cells.items():
                if numeric:
                    from chart_compat import column_name
                    self.assertEqual(actual[f'{column_name(col)}{row}'],value)

    def test_invalid_range_and_empty_zero_are_repaired(self):
        """Remove the invalid apostrophe and restore numeric zero from the cache."""
        source=zipfile.ZipFile(io.BytesIO(workbook_bytes({'Sheet1':{(1,1):('0',True)}})))
        contents={name:source.read(name) for name in source.namelist()}
        sheet=parse_xml(contents['xl/worksheets/sheet1.xml']);sheet.find(f'.//{{{S}}}v').text=None
        contents['xl/worksheets/sheet1.xml']=xml_bytes(sheet)
        contents['xl/tables/table1.xml']=f'<table xmlns="{S}" ref="A1:A1\'"/>'.encode()
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w') as book:
            for name,data in contents.items():book.writestr(name,data)
        chart=ET.Element(q('c','chartSpace'));group=ET.SubElement(ET.SubElement(ET.SubElement(chart,q('c','chart')),q('c','plotArea')),q('c','barChart'))
        ref=ET.SubElement(ET.SubElement(ET.SubElement(group,q('c','ser')),q('c','val')),q('c','numRef'))
        ET.SubElement(ref,q('c','f')).text='Sheet1!$A$1:$A$1'
        cache=ET.SubElement(ref,q('c','numCache'));ET.SubElement(ET.SubElement(cache,q('c','pt'),idx='0'),q('c','v')).text='0'
        ET.SubElement(chart,q('c','externalData'),attrib={q('r','id'):'rId1'})
        part='ppt/charts/chart1.xml';parts={part:xml_bytes(chart),'ppt/embeddings/zero.xlsx':output.getvalue(),rel_path(part):f'<Relationships xmlns="{NS["rel"]}"><Relationship Id="rId1" Target="../embeddings/zero.xlsx" Type="{NS["r"]}/package"/></Relationships>'.encode()}
        repairs=normalize_chart_workbooks(parts)
        self.assertEqual(repairs[0]['ranges'],1);self.assertEqual(repairs[0]['zeroCells'],1)
        with zipfile.ZipFile(io.BytesIO(parts['ppt/embeddings/zero.xlsx'])) as book:
            self.assertEqual(parse_xml(book.read('xl/tables/table1.xml')).get('ref'),'A1:A1')
            self.assertEqual(parse_xml(book.read('xl/worksheets/sheet1.xml')).findtext(f'.//{{{S}}}v'),'0')
