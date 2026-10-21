"""Check the exported OOXML, not just the layout engine's intentions."""
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PPTX = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'output/recreated-slides.pptx'
NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'c': 'http://schemas.openxmlformats.org/drawingml/2006/chart'}


def norm(t):
    """Normalize only whitespace/bullets when comparing responsive template text."""
    return re.sub(r'[\s•]+', '', t or '')


def verify_fidelity(pptx, report):
    """Audit the actual package independently of generator counters.

    Check selection, aspect ratio, internal relationships and hashes. The baseline
    requires byte-identical visual/binary parts, including XML not directly used by
    the renderer. List configured changes in the report."""
    from native_deck import read_parts, relationships, resolve_target, parse_xml, local
    import hashlib
    source = Path(report.get('sourceFile', ROOT/'2606 Context Enriched Slide Repository.pptx'))
    original = read_parts(source)
    actual = read_parts(pptx)
    assert hashlib.sha256(pptx.read_bytes()).hexdigest() == report['outputSha256']
    presentation = parse_xml(actual['ppt/presentation.xml'])
    slides = presentation.findall('p:sldIdLst/p:sldId', NS)
    assert len(slides) == report['counts']['outputSlides']
    size = presentation.find('p:sldSz', NS)
    assert abs(int(size.get('cx'))/int(size.get('cy'))-16/9) < 1e-5
    dangling = []
    for name, payload in actual.items():
        if not name.endswith('.rels'):
            continue
        owner = '' if name == '_rels/.rels' else name.replace('/_rels/', '/')[:-5]
        for relation in parse_xml(payload):
            if relation.get('TargetMode') == 'External':
                continue
            target = resolve_target(owner, relation.get('Target')).split('#')[0]
            if target not in actual:
                dangling.append((name, target))
    assert not dangling, dangling[:10]
    for name in report['changedParts']:
        if name.endswith('.rels') or name == '[Content_Types].xml':
            expected = b'<Types xmlns=' if name == '[Content_Types].xml' else b'<Relationships xmlns='
            assert expected in actual[name], f'Incompatible OPC namespace: {name}'
    changed = sorted(n for n in actual if original.get(n) != actual[n])
    assert changed == sorted(report['changedParts'])
    if report['baselineVisualPartsByteIdentical']:
        assert changed == ['docProps/core.xml']
        assert set(original) == set(actual)
        for name, payload in original.items():
            if name != 'docProps/core.xml':
                assert actual[name] == payload, name
    charts = sum(bool(re.fullmatch(r'ppt/charts/chart\d+\.xml', n)) for n in actual)
    tables = sum(len(parse_xml(actual[f'ppt/slides/slide{n}.xml']).findall('.//a:tbl', NS))
                 for n in report['selection'])
    print(f'PASS: {len(slides)} slides, 16:9, {tables} tables, {charts} source charts; valid internal relationships.')
    print(f'PASS: baseline visual byte identity={report["baselineVisualPartsByteIdentical"]}; {len(changed)} changed parts.')
    if report.get('quality'):
        assert not report['quality']['estimatedOverflow']
        assert len(report['slides']) == len(slides)
        active_charts = sum(len(parse_xml(actual[entry['part']]).findall('.//c:chart', NS)) for entry in report['slides'])
        active_tables = sum(len(parse_xml(actual[entry['part']]).findall('.//a:tbl', NS)) for entry in report['slides'])
        assert active_charts == 26, active_charts
        print(f'PASS: quality: {active_charts} active native charts, {active_tables} active tables, zero estimated overflow.')


_report = json.loads(PPTX.with_suffix('.layout.json').read_text())
if _report.get('mode') == 'fidelity':
    verify_fidelity(PPTX, _report)
    sys.exit(0)


with zipfile.ZipFile(PPTX) as z:
    names = z.namelist()
    slides = sorted((n for n in names if re.fullmatch(r'ppt/slides/slide\d+.xml', n)),
                    key=lambda n: int(re.search(r'(\d+)\.xml', n).group(1)))
    assert len(slides) == 7, len(slides)
    presentation = ET.fromstring(z.read('ppt/presentation.xml'))
    dimensions = presentation.find('p:sldSz', NS)
    assert abs(int(dimensions.get('cx')) / int(dimensions.get('cy')) - 16 / 9) < 1e-5
    roots = [ET.fromstring(z.read(n)) for n in slides]
    assert sum(len(r.findall('.//a:tbl', NS)) for r in roots) == 2
    chart_names = [n for n in names if re.fullmatch(r'ppt/charts/chart\d+.xml', n)]
    assert len(chart_names) == 3
    actual = [norm(''.join(t.text or '' for t in r.findall('.//a:t', NS))) for r in roots]
    source = json.loads((ROOT / 'data/source.json').read_text())['slides']
    # Summary is fully preserved, including all original paragraphs.
    assert norm(source['5']['texts'][1]['text']) in actual[0]
    # Every agenda/comparison cell survives as native table content.
    for output_index, number in [(1, '10'), (3, '38')]:
        for row in source[number]['tables'][0]:
            for cell in row:
                assert norm(cell) in actual[output_index], (number, cell)
    # Every dashboard concern and accomplishment paragraph survives rich text rendering.
    for index in [5, 13, 19, 27, 33, 41]:
        for p in source['68']['texts'][index]['paragraphs']:
            assert norm(p['text']) in actual[6], p['text']
    expected = [[1, 8, 2, 11], [1, 13, 6, 20], [2, 27, 7, 36]]
    for n, values in zip(sorted(chart_names), expected):
        r = ET.fromstring(z.read(n))
        got = [float(v.text) for v in r.findall('.//c:ser/c:val//c:pt/c:v', NS)]
        assert got == values, (got, values)
    assert all(r.find('p:clrMapOvr', NS) is not None for r in roots)
    layout_count = sum(bool(re.fullmatch(r'ppt/slideLayouts/slideLayout\d+.xml', n)) for n in names)
    assert layout_count >= 7
    hidden = roots[-1].get('show') == '0'
    print(f'PASS: 7 slides, 16:9, 2 native tables, 3 native charts, {layout_count} layouts; dashboard hidden={hidden}.')

report = json.loads(PPTX.with_suffix('.layout.json').read_text())
for slide in report['slides']:
    for e in slide['elements']:
        b = e['box']
        assert b['x'] >= -0.001 and b['y'] >= -0.001
        assert b['x'] + b['w'] <= report['slideSize']['width'] + 0.001
        assert b['y'] + b['h'] <= report['slideSize']['height'] + 0.001
        if 'estimatedHeight' in e:
            assert e['estimatedHeight'] <= b['h'] + 0.011, e['id']
print('PASS: native content retained, chart data exact, component bounds and measured text fit.')
