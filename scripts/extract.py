"""Extract source evidence with Python's standard library; never modifies the reference."""
import json
import posixpath
import sys
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
SOURCE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / '2606 Context Enriched Slide Repository.pptx'
SELECTED = [5, 10, 21, 38, 50, 64, 68]
NS = {k: f'http://schemas.openxmlformats.org/{v}' for k, v in {
    'a': 'drawingml/2006/main', 'p': 'presentationml/2006/main',
    'r': 'officeDocument/2006/relationships', 'c': 'drawingml/2006/chart'}.items()}


def geometry_svg(sp, color='EC111A'):
    """Traduz geometrias originais em SVG para os sete templates adaptativos.

    Args: sp é uma forma XML; color é sRGB sem # usado no asset derivado.
    Returns: SVG com viewBox nas unidades originais ou None se não houver path.
    paths guarda subpaths; commands converte move/line/Bezier/close. A largura
    física normalizada em 1000 px evita alocações enormes por causa de EMU.
    Não desenha artwork novo nem modifica o objeto do PPTX de referência.
    """
    geom = sp.find('p:spPr/a:custGeom', NS)
    if geom is None:
        return None
    paths = geom.findall('a:pathLst/a:path', NS)
    if not paths:
        return None
    width, height = paths[0].get('w'), paths[0].get('h')
    if not width or not height:
        return None
    output = []
    for path in paths:
        commands = []
        for command in path:
            tag = command.tag.split('}')[-1]
            points = [f"{p.get('x')},{p.get('y')}" for p in command.findall('a:pt', NS)]
            op = {'moveTo': 'M', 'lnTo': 'L', 'cubicBezTo': 'C', 'quadBezTo': 'Q', 'close': 'Z'}.get(tag)
            if op is None:
                raise ValueError(f'Unsupported source geometry: {tag}')
            commands.append(op + ' '.join(points))
        output.append(f'<path d="{" ".join(commands)}" fill="#{color}" fill-rule="nonzero"/>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{1000*float(height)/float(width):.3f}" viewBox="0 0 {width} {height}">{"".join(output)}</svg>'


def text(node):
    """Extrai o texto por parágrafo de um nó XML, mantendo quebras entre parágrafos."""
    return '\n'.join(''.join(t.text or '' for t in p.findall('.//a:t', NS))
                     for p in node.findall('.//a:p', NS)).strip()


def relationships(z, part):
    """Resolve relações OPC internas da parte em um ZipFile aberto.

    part identifica a parte proprietária; path é sua parte .rels. Retorna mapa
    rId -> caminho normalizado no ZIP, sem buscar URLs ou arquivos externos.
    """
    path = posixpath.join(posixpath.dirname(part), '_rels', posixpath.basename(part) + '.rels')
    if path not in z.namelist():
        return {}
    return {r.get('Id'): posixpath.normpath(posixpath.join(posixpath.dirname(part), r.get('Target')))
            for r in ET.fromstring(z.read(path)) if r.get('TargetMode') != 'External'}


def paragraphs(node):
    """Extrai runs e propriedades explícitas para o modo adaptativo.

    Args: node é uma forma com p:txBody. Returns: parágrafos com text/runs/level/
    bullet. pp representa propriedades de parágrafo; rp, propriedades do run.
    A resolução completa de estilos herdados fica no modo fiel, sem achatamento.
    """
    result = []
    for p in node.findall('./p:txBody/a:p', NS):
        pp = p.find('a:pPr', NS)
        runs = []
        for r in p:
            t = r.find('a:t', NS)
            if t is None:
                continue
            rp = r.find('a:rPr', NS)
            attrs = dict(rp.attrib) if rp is not None else {}
            color = rp.find('a:solidFill/a:srgbClr', NS) if rp is not None else None
            if color is not None:
                attrs['color'] = color.get('val')
            runs.append({'text': t.text or '', 'style': attrs})
        result.append({'text': ''.join(r['text'] for r in runs), 'runs': runs,
                       'level': int(pp.get('lvl', 0)) if pp is not None else 0,
                       'bullet': pp is not None and pp.find('a:buChar', NS) is not None})
    return result


def extract():
    """Extrai os sete exemplos semânticos e seus assets para data/source.json.

    SELECTED é a lista dos números originais. result separa texto, tabelas,
    gráficos e notas; master/group reaproveitam o logo original. Arquivos SVG e
    metadados são derivados; SOURCE é somente leitura. Retorna None e imprime
    um resumo. Para todos os 71 slides, use native_deck.py catalog.
    """
    (ROOT / 'assets').mkdir(exist_ok=True)
    (ROOT / 'data').mkdir(exist_ok=True)
    with zipfile.ZipFile(SOURCE) as z:
        result = {'source': SOURCE.name, 'slides': {}}
        for number in SELECTED:
            part = f'ppt/slides/slide{number}.xml'
            r = ET.fromstring(z.read(part))
            rels = relationships(z, part)
            slide = {'sourceNumber': number, 'hidden': r.get('show') == '0',
                     'texts': [], 'tables': [], 'pictures': [], 'geometry': [], 'charts': [], 'notes': ''}
            for sp in r.findall('.//p:sp', NS):
                if text(sp):
                    slide['texts'].append({'text': text(sp), 'paragraphs': paragraphs(sp)})
                if number in (50, 64):
                    svg = geometry_svg(sp, 'EC111A' if number == 50 else 'D8D6CA')
                    if svg:
                        name = f'source-{number}-geometry-{len(slide["geometry"])}.svg'
                        (ROOT / 'assets' / name).write_text(svg)
                        slide['geometry'].append('assets/' + name)
            for tbl in r.findall('.//a:tbl', NS):
                slide['tables'].append([[text(cell) for cell in row.findall('a:tc', NS)]
                                        for row in tbl.findall('a:tr', NS)])
            for pic in r.findall('.//p:pic', NS):
                # Prefer the actual SVG over its raster fallback.
                blips = [x for x in pic.iter() if x.tag.split('}')[-1] in ('svgBlip', 'blip')]
                blips.sort(key=lambda x: x.tag.endswith('svgBlip'), reverse=True)
                for blip in blips:
                    target = rels.get(blip.get('{' + NS['r'] + '}embed'))
                    if target:
                        dest = ROOT / 'assets' / posixpath.basename(target)
                        dest.write_bytes(z.read(target))
                        xfrm = pic.find('p:spPr/a:xfrm', NS)
                        bbox = {}
                        if xfrm is not None:
                            for c in xfrm:
                                bbox[c.tag.split('}')[-1]] = dict(c.attrib)
                        slide['pictures'].append({'path': 'assets/' + dest.name, 'bbox': bbox})
                        break
            for chart in r.findall('.//c:chart', NS):
                target = rels[chart.get('{' + NS['r'] + '}id')]
                cr = ET.fromstring(z.read(target))
                for ser in cr.findall('.//c:ser', NS):
                    labels = [v.text for v in ser.findall('c:cat//c:pt/c:v', NS)]
                    values = [float(v.text) for v in ser.findall('c:val//c:pt/c:v', NS)]
                    slide['charts'].append({'labels': labels, 'values': values})
            notes = next((v for v in rels.values() if '/notesSlides/' in v), None)
            if notes:
                slide['notes'] = text(ET.fromstring(z.read(notes)))
            result['slides'][str(number)] = slide
        (ROOT / 'data/source.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        # Reuse the original master logo. Child coordinates are retained in their original group space.
        master = ET.fromstring(z.read('ppt/slideMasters/slideMaster1.xml'))
        group = next(g for g in master.findall('.//p:grpSp', NS) if g.find('.//a:custGeom', NS) is not None)
        gx = group.find('p:grpSpPr/a:xfrm', NS)
        offset, extent = gx.find('a:chOff', NS), gx.find('a:chExt', NS)
        parts = []
        for sp in group.findall('p:sp', NS):
            svg = geometry_svg(sp)
            if not svg:
                continue
            x = sp.find('p:spPr/a:xfrm', NS)
            off, ext = x.find('a:off', NS), x.find('a:ext', NS)
            svg = svg.replace('<svg ', f'<svg x="{off.get("x")}" y="{off.get("y")}" ').replace(
                'width="' + svg.split('width="')[1].split('"')[0] + '"', 'width="' + ext.get('cx') + '"', 1)
            old_h = svg.split('height="')[1].split('"')[0]
            svg = svg.replace(f'height="{old_h}"', f'height="{ext.get("cy")}"', 1)
            parts.append(svg)
        # Central globe is an original preset ellipse in the master logo.
        for sp in group.findall('p:sp', NS):
            geom = sp.find('p:spPr/a:prstGeom', NS)
            if geom is not None and geom.get('prst') == 'ellipse':
                x = sp.find('p:spPr/a:xfrm', NS)
                off, ext = x.find('a:off', NS), x.find('a:ext', NS)
                parts.append(f'<ellipse cx="{float(off.get("x"))+float(ext.get("cx"))/2}" cy="{float(off.get("y"))+float(ext.get("cy"))/2}" rx="{float(ext.get("cx"))/2}" ry="{float(ext.get("cy"))/2}" fill="#EC111A"/>')
        (ROOT / 'assets/logo.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{extent.get("cx")}" height="{extent.get("cy")}" viewBox="{offset.get("x")} {offset.get("y")} {extent.get("cx")} {extent.get("cy")}">{"".join(parts)}</svg>')
    print('Extracted seven slides and original assets into data/source.json and assets/')


if __name__ == '__main__':
    extract()
