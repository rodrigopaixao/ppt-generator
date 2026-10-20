"""Preserva e configura DrawingML original sem rasterizar os slides.

O PptxGenJS não importa uma apresentação existente de maneira sem perdas. Este
adaptador recebe o pacote gerado pela biblioteca e restaura as partes nativas
da referência. Somente partes explicitamente configuradas são serializadas de
novo. Assim, um build sem overrides conserva os bytes de todos os componentes
visuais, inclusive recursos que o PptxGenJS não sabe reconstruir.

Unidades: ``box`` usa polegadas; ``localBox`` usa EMU (914400 por polegada);
``grid`` usa colunas/linhas fracionárias. ``eN`` é o ID nativo p:cNvPr/@id,
estável dentro do slide/layout/master. Grupos mantêm seus filhos e coordenadas.
"""
import argparse
import copy
import hashlib
import io
import json
import math
import posixpath
import re
import zipfile
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
EMU = 914400
NS = {
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'c': 'http://schemas.openxmlformats.org/drawingml/2006/chart',
    'rel': 'http://schemas.openxmlformats.org/package/2006/relationships',
    'ct': 'http://schemas.openxmlformats.org/package/2006/content-types',
    's': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    'asvg': 'http://schemas.microsoft.com/office/drawing/2016/SVG/main',
}
for _prefix in ('a', 'p', 'r', 'c', 'asvg'):
    ET.register_namespace(_prefix, NS[_prefix])

SOURCE = ROOT / '2606 Context Enriched Slide Repository.pptx'
KINDS = {'sp': 'shape', 'pic': 'image', 'grpSp': 'group', 'cxnSp': 'connector',
         'graphicFrame': 'frame', 'AlternateContent': 'alternate'}
NAMESPACE_HINTS = dict(NS)


def parse_xml(payload):
    """Lê XML e lembra seus prefixos, inclusive os usados só por mc:Ignorable.

    ElementTree normalmente descarta declarações não usadas em tags. Guardá-las
    evita um PPTX que um renderizador aceite mas PowerPoint peça para reparar.
    """
    for _, (prefix, uri) in ET.iterparse(io.BytesIO(payload), events=('start-ns',)):
        if prefix:
            NAMESPACE_HINTS[prefix] = uri
            if not re.fullmatch(r'ns\d+', prefix):
                ET.register_namespace(prefix, uri)
    return ET.fromstring(payload)


def q(prefix, name):
    """Retorna uma tag expandida de namespace.

    Args: prefix é uma chave de NS; name é o nome local da tag/atributo.
    Returns: string ``{URI}name``, aceita pelo ElementTree.
    """
    return '{' + NS[prefix] + '}' + name


def local(tag):
    """Remove somente o namespace de uma tag XML; não modifica o documento."""
    return tag.rsplit('}', 1)[-1]


def xml_bytes(node):
    """Serializa uma árvore modificada em UTF-8 com declaração XML.

    Usada apenas para partes alteradas. Partes intocadas mantêm seus bytes.
    """
    namespace = node.tag.split('}')[0].lstrip('{')
    if namespace in (NS['rel'], NS['ct'], NS['s'],
                     'http://schemas.openxmlformats.org/officeDocument/2006/extended-properties'):
        # Alguns leitores OPC detectam o pacote por nomes lexicais sem prefixo.
        # Manter o namespace padrão evita arquivos válidos em XML mas não abertos.
        ET.register_namespace('', namespace)
    value = ET.tostring(node, encoding='unicode')
    required = set()
    for element in node.iter():
        for key, attr in element.attrib.items():
            if local(key) in ('Ignorable', 'Requires', 'PreserveElements', 'ProcessContent'):
                required.update(token.split(':')[0] for token in attr.split())
    missing = []
    for prefix in required:
        if not re.search(r'xmlns:'+re.escape(prefix)+r'=', value):
            if prefix not in NAMESPACE_HINTS:
                raise ValueError(f'Prefixo de compatibilidade sem declaração: {prefix}')
            missing.append(f' xmlns:{prefix}="{NAMESPACE_HINTS[prefix]}"')
    if missing:
        end = value.find('>')
        index = end-1 if value[end-1] == '/' else end
        value = value[:index]+''.join(missing)+value[index:]
    return ('<?xml version="1.0" encoding="utf-8"?>\n'+value).encode('utf-8')


def rel_path(part):
    """Calcula o nome da parte .rels correspondente a part dentro do ZIP."""
    return posixpath.join(posixpath.dirname(part), '_rels', posixpath.basename(part) + '.rels')


def resolve_target(part, target):
    """Resolve um Target OPC relativo à sua parte, sem acessar o filesystem."""
    return posixpath.normpath(posixpath.join(posixpath.dirname(part), target)).lstrip('/')


def relationships(parts, part):
    """Lê os relacionamentos internos de uma parte.

    Args: parts mapeia nomes ZIP para bytes; part é a parte proprietária.
    Returns: mapa rId -> {target, type}; referências externas são ignoradas.
    """
    payload = parts.get(rel_path(part))
    if payload is None:
        return {}
    return {r.get('Id'): {'target': resolve_target(part, r.get('Target')),
                         'type': r.get('Type')}
            for r in parse_xml(payload) if r.get('TargetMode') != 'External'}


def identity(node):
    """Lê o ID/nome/estado oculto do objeto DrawingML, sem confundir IDs filhos."""
    for child in node:
        if local(child.tag).startswith('nv'):
            prop = child.find('p:cNvPr', NS)
            if prop is not None:
                return {'id': 'e' + prop.get('id'), 'name': prop.get('name', ''),
                        'hidden': prop.get('hidden') == '1'}
    return None


def text_of(node):
    """Extrai parágrafos visíveis sem interpretar fórmulas ou instruções em texto."""
    return '\n'.join(''.join(t.text or '' for t in p.iter(q('a', 't')))
                     for p in node.iter(q('a', 'p')))


def drawable_children(node):
    """Itera somente objetos de desenho diretos, preservando ordem de sobreposição.

    Não percorre tabelas/caches como se suas células fossem objetos de slide.
    """
    return [child for child in node if local(child.tag) in KINDS]


def transform_of(node):
    """Encontra o xfrm próprio do objeto, distinguindo formas, frames e grupos."""
    for selector in ('p:spPr/a:xfrm', 'p:xfrm', 'p:grpSpPr/a:xfrm'):
        value = node.find(selector, NS)
        if value is not None:
            return value
    return None


def placeholder_of(node):
    """Retorna a chave de placeholder (tipo, índice), ou None para um objeto comum."""
    for child in node:
        if local(child.tag).startswith('nv'):
            ph = child.find('p:nvPr/p:ph', NS)
            if ph is not None:
                return {'type': ph.get('type', 'obj'), 'idx': ph.get('idx', '0')}
    return None


def inherited_node(node, ancestors):
    """Procura a geometria herdada no layout e depois no master.

    ancestors é uma lista ordenada [layout, master]. Primeiro tenta índice de
    placeholder, depois tipo. Retorna também a origem para auditoria do catálogo.
    """
    ph = placeholder_of(node)
    if not ph:
        return None, None
    for part, root in ancestors:
        candidates = [n for n in root.iter() if local(n.tag) in KINDS and placeholder_of(n)]
        for key in ('idx', 'type'):
            for candidate in candidates:
                if placeholder_of(candidate)[key] == ph[key] and transform_of(candidate) is not None:
                    return candidate, part
    return None, None


def compose(a, b):
    """Multiplica matrizes afins 2D (a,b,c,d,e,f) na ordem pai × filho.

    O resultado transforma coordenadas locais do filho em coordenadas do slide.
    """
    aa, ab, ac, ad, ae, af = a
    ba, bb, bc, bd, be, bf = b
    return (aa*ba + ac*bb, ab*ba + ad*bb, aa*bc + ac*bd,
            ab*bc + ad*bd, aa*be + ac*bf + ae, ab*be + ad*bf + af)


def point(matrix, x, y):
    """Aplica uma transformação afim a um ponto local x,y em EMU."""
    a, b, c, d, e, f = matrix
    return a*x + c*y + e, b*x + d*y + f


def inverse(matrix):
    """Inverte uma transformação afim. Rejeita grupos degenerados (escala zero)."""
    a, b, c, d, e, f = matrix
    determinant = a*d - b*c
    if abs(determinant) < 1e-12:
        raise ValueError('Transformação de grupo não invertível')
    return (d/determinant, -b/determinant, -c/determinant, a/determinant,
            (c*f-d*e)/determinant, (b*e-a*f)/determinant)


def transform_values(xfrm):
    """Lê off/ext de xfrm. Valores ausentes usam zero, sem alterar a herança XML."""
    off, ext = xfrm.find('a:off', NS), xfrm.find('a:ext', NS)
    return (float(off.get('x', 0)) if off is not None else 0,
            float(off.get('y', 0)) if off is not None else 0,
            float(ext.get('cx', 0)) if ext is not None else 0,
            float(ext.get('cy', 0)) if ext is not None else 0)


def group_matrix(xfrm):
    """Calcula escala, translação, rotação e espelhamento de um grupo nativo.

    off/ext descrevem o grupo no pai; chOff/chExt descrevem seu espaço interno.
    A rotação DrawingML está em 1/60000 de grau. Nenhum valor é arredondado aqui.
    """
    x, y, w, h = transform_values(xfrm)
    co, ce = xfrm.find('a:chOff', NS), xfrm.find('a:chExt', NS)
    ox = float(co.get('x', 0)) if co is not None else 0
    oy = float(co.get('y', 0)) if co is not None else 0
    cw = float(ce.get('cx', w)) if ce is not None else w
    ch = float(ce.get('cy', h)) if ce is not None else h
    sx, sy = w/(cw or 1), h/(ch or 1)
    base = (sx, 0, 0, sy, x-ox*sx, y-oy*sy)
    angle = math.radians(float(xfrm.get('rot', 0))/60000)
    fx = -1 if xfrm.get('flipH') == '1' else 1
    fy = -1 if xfrm.get('flipV') == '1' else 1
    cos, sin = math.cos(angle), math.sin(angle)
    rotation = (cos*fx, sin*fx, -sin*fy, cos*fy, 0, 0)
    center = (x+w/2, y+h/2)
    rotation = (*rotation[:4], center[0]-rotation[0]*center[0]-rotation[2]*center[1],
                center[1]-rotation[1]*center[0]-rotation[3]*center[1])
    return compose(rotation, base)


def box_for(xfrm, parent):
    """Converte o retângulo local em box no slide, em polegadas.

    box representa o envelope dos cantos após transformações dos grupos. A
    rotação própria do objeto fica no campo rotation do catálogo, separadamente.
    """
    x, y, w, h = transform_values(xfrm)
    corners = [point(parent, x+dx, y+dy) for dx, dy in ((0, 0), (w, 0), (0, h), (w, h))]
    xs, ys = zip(*corners)
    return dict(x=min(xs)/EMU, y=min(ys)/EMU, w=(max(xs)-min(xs))/EMU, h=(max(ys)-min(ys))/EMU)


def ancestors_for(parts, part):
    """Resolve a cadeia slide -> layout -> master, sem achatar seus estilos."""
    if '/slideMasters/' in part:
        return []
    result, current = [], part
    chain = ('/slideMaster',) if '/slideLayouts/' in part else ('/slideLayout', '/slideMaster')
    for suffix in chain:
        relation = next((r for r in relationships(parts, current).values() if r['type'].endswith(suffix)), None)
        if relation:
            current = relation['target']
            result.append((current, parse_xml(parts[current])))
    return result


def scene_nodes(root, ancestors=()):
    """Indexa recursivamente os objetos nativos com seus pais e matrizes.

    Returns: mapa eID -> registro interno contendo node (XML), parent (XML),
    parentMatrix, effectiveTransform e inheritedFrom. Esses objetos não são
    gravados em JSON diretamente; describe_scene produz a visão serializável.
    """
    tree = root.find('p:cSld/p:spTree', NS)
    result = {}

    def visit(container, parent_matrix, parent_id=None):
        """Percorre um grupo em ordem de desenho e acumula a transformação dos pais."""
        for node in drawable_children(container):
            ident = identity(node)
            if not ident:
                continue
            own = transform_of(node)
            inherited, inherited_part = inherited_node(node, ancestors) if own is None else (None, None)
            effective = own if own is not None else transform_of(inherited) if inherited is not None else None
            if ident['id'] in result:
                raise ValueError(f'ID DrawingML duplicado: {ident["id"]}')
            result[ident['id']] = {**ident, 'node': node, 'parent': container,
                'parentId': parent_id, 'parentMatrix': parent_matrix,
                'effectiveTransform': effective, 'inheritedFrom': inherited_part}
            if local(node.tag) == 'grpSp':
                matrix = compose(parent_matrix, group_matrix(effective)) if effective is not None else parent_matrix
                visit(node, matrix, ident['id'])

    if tree is not None:
        visit(tree, (1, 0, 0, 1, 0, 0))
    return result


def reference_typography(node, ancestors):
    """Resolve tamanhos em pt por parágrafo na referência, antes de aplicar tokens.

    A precedência é run, parágrafo, lista local, placeholder do layout/master e
    txStyles do master. O catálogo registra a origem para não depender de autofit.
    """
    body = node.find('p:txBody', NS)
    if body is None:
        return None
    ph = placeholder_of(node)
    inherited = []
    if ph:
        for _, root in ancestors:
            candidates = [n for n in root.iter(q('p','sp')) if placeholder_of(n)]
            match = next((n for n in candidates if placeholder_of(n)['idx'] == ph['idx']), None)
            if match is None:
                match = next((n for n in candidates if placeholder_of(n)['type'] == ph['type']), None)
            if match is not None:
                inherited.append(match)
    paragraphs = []
    for paragraph in body.findall('a:p', NS):
        pp = paragraph.find('a:pPr', NS)
        level = int(pp.get('lvl',0)) if pp is not None else 0
        candidates = [paragraph.find('a:pPr/a:defRPr',NS), body.find(f'a:lstStyle/a:lvl{level+1}pPr/a:defRPr',NS)]
        for parent in inherited:
            candidates.extend([parent.find('p:txBody/a:p/a:pPr/a:defRPr',NS),
                parent.find(f'p:txBody/a:lstStyle/a:lvl{level+1}pPr/a:defRPr',NS)])
        style = 'titleStyle' if ph and ph['type'] in ('title','ctrTitle') else 'bodyStyle' if ph and ph['type']=='body' else 'otherStyle'
        for _, root in ancestors:
            candidates.append(root.find(f'p:txStyles/p:{style}/a:lvl{level+1}pPr/a:defRPr',NS))
        default = next((float(n.get('sz'))/100 for n in candidates if n is not None and n.get('sz')), None)
        runs = paragraph.findall('a:r',NS)+paragraph.findall('a:fld',NS)
        sizes = []
        for run in runs:
            prop = run.find('a:rPr',NS)
            value = float(prop.get('sz'))/100 if prop is not None and prop.get('sz') else default
            if value is not None:
                sizes.append(value)
        if not sizes:
            sizes = [float(n.get('sz'))/100 for n in paragraph.iter() if n.get('sz')] or ([default] if default else [])
        paragraphs.append({'text':text_of(paragraph), 'size':max(sizes) if sizes else None, 'runSizes':sizes})
    return {'paragraphs':paragraphs, 'size':next((p['size'] for p in paragraphs if p['size']), None)}


def describe_scene(parts, part, dimensions):
    """Produz o catálogo configurável de uma parte, mantendo IDs e hierarquia.

    dimensions é {width,height}, em polegadas. As posições grid são fracionárias
    em 14×9, sem snap: arredondar o original destruiria a fidelidade.
    """
    root = parse_xml(parts[part])
    ancestors = ancestors_for(parts, part)
    records = scene_nodes(root, ancestors)
    rels = relationships(parts, part)
    output = []
    for ident, record in records.items():
        node, xf = record['node'], record['effectiveTransform']
        kind = KINDS[local(node.tag)]
        if node.find('.//a:tbl', NS) is not None and kind == 'frame':
            kind = 'table'
        elif node.find('.//c:chart', NS) is not None and kind == 'frame':
            kind = 'chart'
        item = {key: record[key] for key in ('id', 'name', 'hidden', 'parentId', 'inheritedFrom')}
        item.update(kind=kind, text=text_of(node) if kind != 'group' else '',
                    placeholder=placeholder_of(node),
                    typography=reference_typography(node, ancestors) if kind == 'shape' else None,
                    sourcePart=part,
                    relations=[{'id': key, **value} for key, value in rels.items()
                               if any(key in e.attrib.values() for e in node.iter())])
        if xf is not None:
            box = box_for(xf, record['parentMatrix'])
            item.update(box=box, rotation=float(xf.get('rot', 0))/60000,
                grid={'col': box['x']/dimensions['width']*14,
                      'row': box['y']/dimensions['height']*9,
                      'colSpan': box['w']/dimensions['width']*14,
                      'rowSpan': box['h']/dimensions['height']*9})
        if kind == 'table':
            item['headerFontSizes'] = [max([float(n.get('sz'))/100 for n in cell.iter() if n.get('sz')] or [10]) for cell in node.findall('.//a:tbl/a:tr', NS)[0].findall('a:tc', NS)]
            item['cells'] = [[text_of(c) for c in r.findall('a:tc', NS)]
                             for r in node.findall('.//a:tbl/a:tr', NS)]
        if kind == 'chart':
            chart = node.find('.//c:chart', NS)
            item['chartPart'] = rels[chart.get(q('r', 'id'))]['target']
        output.append(item)
    return output


def read_parts(source):
    """Lê um pacote OPC em memória. Não extrai arquivos e não altera a referência."""
    with zipfile.ZipFile(source) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def chart_sources(parts):
    """Extrai dados originais de gráficos para recomposição PptxGenJS.

    Retorna tipo, agrupamento, nomes, categorias e valores sem arredondar.
    O arquivo derivado nunca é uma fonte manual de números: cada catalogação
    o regenera a partir do mesmo PPTX cujo hash aparece no manifesto.
    """
    output = {}
    for name, payload in parts.items():
        if not re.fullmatch(r'ppt/charts/chart\d+\.xml', name):
            continue
        root, groups = parse_xml(payload), []
        for group in root.findall('c:chart/c:plotArea/*', NS):
            if not local(group.tag).endswith('Chart'):
                continue
            series = []
            for node in group.findall('c:ser', NS):
                color = node.find('c:spPr/a:solidFill/a:srgbClr', NS)
                series.append({'name': node.findtext('c:tx/c:v', default='', namespaces=NS),
                    'labels': [p.findtext('c:v', namespaces=NS) for p in node.findall('c:cat//c:pt', NS)],
                    'values': [float(p.findtext('c:v', namespaces=NS)) for p in node.findall('c:val//c:pt', NS)],
                    'color': color.get('val') if color is not None else None})
            grouping = group.find('c:grouping', NS)
            groups.append({'type': local(group.tag), 'grouping': grouping.get('val') if grouping is not None else '', 'series': series})
        output[name] = groups
    return output


def write_json_atomic(destination, value):
    """Publica JSON completo por rename, seguro para builds simultâneos.

    destination é Path; value precisa ser serializável. O temporário fica no
    mesmo filesystem e é removido em falhas. Leitores nunca veem JSON parcial.
    """
    destination = Path(destination)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=destination.parent,
                                     prefix='.catalog-', delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, ensure_ascii=False, indent=2)
    try:
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def source_catalog(source=SOURCE, output=ROOT/'data/catalog.json'):
    """Cataloga todos os slides, layouts, masters e recursos do PPTX.

    Efeitos: grava catalog.json e data/slides/NNN.json. O SHA-256 identifica a
    referência usada. Títulos são rótulos de busca; não reescrevem o conteúdo.
    Returns: dicionário serializável com dimensões, contagens e cenas completas.
    """
    source = Path(source)
    parts = read_parts(source)
    presentation = parse_xml(parts['ppt/presentation.xml'])
    size = presentation.find('p:sldSz', NS)
    dimensions = {'width': int(size.get('cx'))/EMU, 'height': int(size.get('cy'))/EMU}
    rels = relationships(parts, 'ppt/presentation.xml')
    slides = []
    for number, entry in enumerate(presentation.findall('p:sldIdLst/p:sldId', NS), 1):
        part = rels[entry.get(q('r', 'id'))]['target']
        root = parse_xml(parts[part])
        scene = describe_scene(parts, part, dimensions)
        title = next((e['text'] for e in scene if e['placeholder'] and
                      e['placeholder']['type'] in ('title', 'ctrTitle')), '')
        if not title:
            title = next((e['text'] for e in scene if e['text'] and len(e['text']) > 3), f'Slide {number}')
        ancestors = ancestors_for(parts, part)
        slides.append({'number': number, 'part': part, 'hidden': root.get('show') == '0',
            'title': title, 'layout': ancestors[0][0] if ancestors else None,
            'master': ancestors[1][0] if len(ancestors) > 1 else None, 'elements': scene})
    layouts, masters = {}, {}
    for part in parts:
        if re.fullmatch(r'ppt/slideLayouts/slideLayout\d+\.xml', part):
            layout_root = parse_xml(parts[part])
            common = layout_root.find('p:cSld', NS)
            layouts[Path(part).stem] = {'part': part, 'name': common.get('name', '') if common is not None else '',
                'type': layout_root.get('type'), 'elements': describe_scene(parts, part, dimensions)}
        if re.fullmatch(r'ppt/slideMasters/slideMaster\d+\.xml', part):
            masters[Path(part).stem] = {'part': part, 'elements': describe_scene(parts, part, dimensions)}
    result = {'schemaVersion': 1, 'source': source.name,
        'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'slide': dimensions,
        'grid': {'columns': 14, 'rows': 9}, 'slides': slides, 'layouts': layouts, 'masters': masters,
        'counts': {'slides': len(slides), 'layouts': len(layouts), 'masters': len(masters),
            'elements': sum(len(s['elements']) for s in slides),
            'charts': sum(bool(re.fullmatch(r'ppt/charts/chart\d+\.xml', p)) for p in parts),
            'tables': sum(e['kind'] == 'table' for s in slides for e in s['elements'])}}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    result['chartSources'] = chart_sources(parts)
    write_json_atomic(output, result)
    write_json_atomic(output.parent/'chart-source.json', result['chartSources'])
    per_slide = output.parent/'slides'
    per_slide.mkdir(exist_ok=True)
    for slide in slides:
        write_json_atomic(per_slide/f'{slide["number"]:03}.json', slide)
    registry = [{'id': f'source-{slide["number"]:03}', 'sourceSlide': slide['number'],
                 'title': slide['title'], 'layout': Path(slide['layout']).stem,
                 'master': Path(slide['master']).stem} for slide in slides]
    write_json_atomic(output.parent/'templates.json', registry)
    return result


def ensure(parent, tag):
    """Obtém um filho direto ou o cria. tag precisa estar em formato expandido."""
    node = parent.find(tag)
    return node if node is not None else ET.SubElement(parent, tag)


def set_color(parent, color):
    """Define um preenchimento sólido sRGB e remove opções de fill conflitantes."""
    if not re.fullmatch(r'[0-9a-fA-F]{6}', color):
        raise ValueError(f'Cor inválida: {color}')
    insertion = None
    for index, child in enumerate(list(parent)):
        if local(child.tag) in ('solidFill', 'noFill', 'gradFill', 'pattFill', 'blipFill', 'grpFill'):
            if insertion is None:
                insertion = index
            parent.remove(child)
    if insertion is None:
        before = {'spPr': {'ln', 'effectLst', 'effectDag', 'scene3d', 'sp3d', 'extLst'},
                  'rPr': {'effectLst', 'highlight', 'latin', 'ea', 'cs', 'sym', 'hlinkClick', 'extLst'},
                  'defRPr': {'effectLst', 'highlight', 'latin', 'ea', 'cs', 'sym', 'extLst'}}
        insertion = next((i for i, child in enumerate(parent)
                          if local(child.tag) in before.get(local(parent.tag), set())),
                         0 if local(parent.tag) in ('ln', 'bgPr') else len(parent))
    fill = ET.Element(q('a', 'solidFill'))
    parent.insert(insertion, fill)
    ET.SubElement(fill, q('a', 'srgbClr'), val=color.upper())


def replace_text(node, value):
    """Substitui texto mantendo os estilos do primeiro parágrafo/run como base.

    Args: node é forma/célula/txBody; value é string, com \n para novos parágrafos.
    A substituição integral é intencional: para manter ênfases distintas, use
    textRuns ou textReplacements, que editam os runs individualmente.
    """
    body = node if local(node.tag) in ('txBody', 'rich') else node.find('p:txBody', NS)
    if body is None:
        body = node.find('a:txBody', NS)
    if body is None:
        raise ValueError('Objeto não possui um corpo de texto configurável')
    existing = body.findall('a:p', NS)
    basis = copy.deepcopy(existing[0]) if existing else ET.Element(q('a', 'p'))
    for p in existing:
        body.remove(p)
    for line in str(value).split('\n'):
        paragraph = copy.deepcopy(basis)
        run_style = paragraph.find('a:r/a:rPr', NS)
        run_style = copy.deepcopy(run_style) if run_style is not None else None
        for child in list(paragraph):
            if local(child.tag) not in ('pPr',):
                paragraph.remove(child)
        run = ET.SubElement(paragraph, q('a', 'r'))
        if run_style is not None:
            run.append(run_style)
        ET.SubElement(run, q('a', 't')).text = line
        body.append(paragraph)


def text_style(node, style):
    """Materializa estilo de texto nos runs e padrões do objeto.

    style aceita fontFace, fontSize (pt), bold, italic, color, align, rotation,
    margin (polegadas), vertical e wrap. Variáveis rpr/pp representam propriedades
    de run/parágrafo. Opções desconhecidas falham para evitar configuração ignorada.
    """
    allowed = {'fontFace', 'fontSize', 'bold', 'italic', 'color', 'align', 'margin', 'vertical', 'wrap'}
    unknown = set(style)-allowed
    if unknown:
        raise ValueError(f'Opções textStyle desconhecidas: {unknown}')
    for p in node.iter(q('a', 'p')):
        pp = p.find('a:pPr', NS)
        if pp is None:
            pp = ET.Element(q('a', 'pPr'))
            p.insert(0, pp)
        if 'align' in style:
            pp.set('algn', {'left': 'l', 'center': 'ctr', 'right': 'r', 'justify': 'just'}[style['align']])
        props = [ensure(pp, q('a', 'defRPr'))]
        for run in p:
            if local(run.tag) in ('r', 'fld'):
                rpr = run.find('a:rPr', NS)
                if rpr is None:
                    rpr = ET.Element(q('a', 'rPr'))
                    run.insert(0, rpr)
                props.append(rpr)
        for rpr in props:
            if 'fontSize' in style:
                if float(style['fontSize']) <= 0:
                    raise ValueError('fontSize deve ser positivo')
                rpr.set('sz', str(round(style['fontSize']*100)))
            for key, attr in [('bold', 'b'), ('italic', 'i')]:
                if key in style:
                    rpr.set(attr, '1' if style[key] else '0')
            if 'fontFace' in style:
                ensure(rpr, q('a', 'latin')).set('typeface', style['fontFace'])
            if 'color' in style:
                set_color(rpr, style['color'])
    for body in node.iter(q('a', 'bodyPr')):
        if 'vertical' in style:
            body.set('anchor', {'top': 't', 'middle': 'ctr', 'bottom': 'b'}[style['vertical']])
        if 'wrap' in style:
            body.set('wrap', 'square' if style['wrap'] else 'none')
        if 'margin' in style:
            for attr in ('lIns', 'rIns', 'tIns', 'bIns'):
                body.set(attr, str(round(float(style['margin'])*EMU)))


def materialize_transform(record):
    """Cria geometria própria para um placeholder que antes herdava do layout.

    Retorna xfrm editável. Copia a geometria herdada antes de alterar, preservando
    rotação, espelhamento e, para grupos, o espaço interno chOff/chExt.
    """
    node = record['node']
    own = transform_of(node)
    if own is not None:
        return own
    if record['effectiveTransform'] is None:
        raise ValueError(f'{record["id"]} não possui geometria nem herança resolvível')
    own = copy.deepcopy(record['effectiveTransform'])
    if local(node.tag) == 'graphicFrame':
        own.tag = q('p', 'xfrm')
        node.insert(1, own)
    else:
        ensure(node, q('p', 'spPr')).insert(0, own)
    return own


def apply_box(record, patch, grid, slide_size):
    """Aplica box global, grid fracionário ou localBox ao xfrm original.

    box usa polegadas no slide. localBox usa EMU no espaço do pai. grid usa a
    região de conteúdo definida por grid.marginX/Y e gapX/Y (padrão zero no modo
    fiel). Para filhos de grupos rotacionados use localBox para controle exato.
    """
    xf = materialize_transform(record)
    current = dict(zip(('x', 'y', 'w', 'h'), transform_values(xf)))
    if 'localBox' in patch:
        current.update(patch['localBox'])
    else:
        box = box_for(xf, record['parentMatrix'])
        if 'grid' in patch:
            gp = patch['grid']
            cols, rows = grid.get('columns', 14), grid.get('rows', 9)
            mx, my = grid.get('marginX', 0), grid.get('marginY', 0)
            gx, gy = grid.get('gapX', 0), grid.get('gapY', 0)
            cw = (slide_size['width']-2*mx-(cols-1)*gx)/cols
            rh = (slide_size['height']-2*my-(rows-1)*gy)/rows
            if cw <= 0 or rh <= 0:
                raise ValueError('Grid sem área útil')
            col, row = gp['col'], gp['row']
            cs, rs = gp.get('colSpan', 1), gp.get('rowSpan', 1)
            if min(col, row) < 0 or min(cs, rs) <= 0 or col+cs > cols or row+rs > rows:
                raise ValueError('Posicionamento ultrapassa o grid')
            box = dict(x=mx+col*(cw+gx), y=my+row*(rh+gy),
                       w=cs*(cw+gx)-gx, h=rs*(rh+gy)-gy)
        box.update(patch.get('box', {}))
        parent = record['parentMatrix']
        inv = inverse(parent)
        cx, cy = point(inv, (box['x']+box['w']/2)*EMU, (box['y']+box['h']/2)*EMU)
        sx, sy = math.hypot(parent[0], parent[1]), math.hypot(parent[2], parent[3])
        w, h = box['w']*EMU/sx, box['h']*EMU/sy
        current = dict(x=cx-w/2, y=cy-h/2, w=w, h=h)
    if current['w'] < 0 or current['h'] < 0:
        raise ValueError('Dimensões negativas não são permitidas')
    off, ext = ensure(xf, q('a', 'off')), ensure(xf, q('a', 'ext'))
    off.attrib.update(x=str(round(current['x'])), y=str(round(current['y'])))
    ext.attrib.update(cx=str(round(current['w'])), cy=str(round(current['h'])))


def patch_table(node, patch):
    """Atualiza células e dimensões de uma tabela nativa, mantendo estilos.

    rows substitui valores e permite mais/menos linhas clonando a última linha.
    cells usa chaves 'linha.coluna' (base zero) para text/fill/textStyle. Larguras
    e alturas são polegadas; a quantidade de colunas precisa ser preservada.
    """
    unknown = set(patch)-{'rows', 'cells', 'columnWidths', 'rowHeights'}
    if unknown:
        raise ValueError(f'Opções de tabela desconhecidas: {unknown}')
    table = node.find('.//a:tbl', NS)
    if table is None:
        raise ValueError('Objeto não é uma tabela')
    columns = table.findall('a:tblGrid/a:gridCol', NS)
    original_height = sum(int(row.get('h', 0)) for row in table.findall('a:tr', NS))
    if 'rows' in patch:
        values = patch['rows']
        if not values or any(len(row) != len(columns) for row in values):
            raise ValueError('rows precisa manter o número de colunas e ter pelo menos uma linha')
        existing = table.findall('a:tr', NS)
        while len(existing) < len(values):
            clone = copy.deepcopy(existing[-1])
            table.append(clone)
            existing.append(clone)
        for row in existing[len(values):]:
            table.remove(row)
        for row, row_values in zip(existing, values):
            for cell, value in zip(row.findall('a:tc', NS), row_values):
                replace_text(cell, value)
    rows = table.findall('a:tr', NS)
    if 'rows' in patch and 'rowHeights' not in patch:
        total = sum(int(row.get('h', 0)) for row in rows)
        for row in rows:
            row.set('h', str(round(int(row.get('h', 0))*original_height/(total or 1))))
    for key, cell_patch in patch.get('cells', {}).items():
        if set(cell_patch)-{'text', 'fill', 'textStyle'}:
            raise ValueError(f'Opções de célula desconhecidas: {key}')
        r, c = map(int, key.split('.'))
        if r < 0 or c < 0:
            raise ValueError('Índices de célula precisam ser não negativos')
        cell = rows[r].findall('a:tc', NS)[c]
        if 'text' in cell_patch:
            replace_text(cell, cell_patch['text'])
        if 'fill' in cell_patch:
            set_color(ensure(cell, q('a', 'tcPr')), cell_patch['fill'])
        if 'textStyle' in cell_patch:
            text_style(cell, cell_patch['textStyle'])
    for key, nodes, attr in [('columnWidths', columns, 'w'), ('rowHeights', rows, 'h')]:
        if key in patch:
            if len(patch[key]) != len(nodes) or any(float(v) <= 0 for v in patch[key]):
                raise ValueError(f'{key} precisa ter um valor positivo por coluna/linha')
            for item, value in zip(nodes, patch[key]):
                item.set(attr, str(round(value*EMU)))


def add_content_type(parts, name, content_type):
    """Registra uma parte nova no manifesto OPC, evitando overrides duplicados."""
    root = parse_xml(parts['[Content_Types].xml'])
    full = '/' + name
    if not any(c.get('PartName') == full for c in root):
        ET.SubElement(root, q('ct', 'Override'), PartName=full, ContentType=content_type)
    parts['[Content_Types].xml'] = xml_bytes(root)


def replace_relation(parts, owner, rid, target):
    """Redireciona um relacionamento existente para uma parte privada nova."""
    name = rel_path(owner)
    root = parse_xml(parts[name])
    relation = next(r for r in root if r.get('Id') == rid)
    relation.set('Target', posixpath.relpath(target, posixpath.dirname(owner)))
    parts[name] = xml_bytes(root)


def workbook_cells(payload, updates):
    """Sincroniza células XLSX referidas pelos caches de um gráfico.

    updates contém tuplas (fórmula A1 de uma célula/range, valores). Cada range
    deve ter a mesma quantidade de valores. Escreve inlineStr para rótulos e
    números para medidas. Mantém todas as outras partes e células do workbook.
    """
    parts = {}
    with zipfile.ZipFile(__import__('io').BytesIO(payload)) as archive:
        parts = {n: archive.read(n) for n in archive.namelist()}
    book = parse_xml(parts['xl/workbook.xml'])
    rels = relationships(parts, 'xl/workbook.xml')
    sheets = {s.get('name'): rels[s.get(q('r', 'id'))]['target']
              for s in book.findall('s:sheets/s:sheet', NS)}
    for formula, values in updates:
        match = re.fullmatch(r"('?[^!]+?'?)!\$?([A-Z]+)\$?(\d+)(?::\$?([A-Z]+)\$?(\d+))?", formula)
        if not match:
            raise ValueError(f'Fórmula de gráfico não suportada: {formula}')
        sheet, c1, r1, c2, r2 = match.groups()
        c2, r2 = c2 or c1, int(r2 or r1)
        r1 = int(r1)
        if c1 != c2 and r1 != r2:
            raise ValueError('Ranges de gráfico precisam ser vetores')
        addresses = [f'{c1}{i}' for i in range(r1, r2+1)] if c1 == c2 else [
            f'{_column_label(i)}{r1}' for i in range(_column_number(c1), _column_number(c2)+1)]
        if len(addresses) != len(values):
            raise ValueError('Alterar a quantidade de pontos requer atualizar a fórmula explicitamente')
        part = sheets[sheet.strip("'")]
        root = parse_xml(parts[part])
        data = root.find('s:sheetData', NS)
        for address, value in zip(addresses, values):
            cell = root.find(f'.//s:c[@r="{address}"]', NS)
            if cell is None:
                row_no = re.search(r'\d+', address).group()
                row = next((r for r in data if r.get('r') == row_no), None)
                if row is None:
                    row = ET.SubElement(data, q('s', 'row'), r=row_no)
                cell = ET.SubElement(row, q('s', 'c'), r=address)
            for child in list(cell):
                cell.remove(child)
            if isinstance(value, (int, float)):
                cell.attrib.pop('t', None)
                ET.SubElement(cell, q('s', 'v')).text = str(value)
            else:
                cell.set('t', 'inlineStr')
                ET.SubElement(ET.SubElement(cell, q('s', 'is')), q('s', 't')).text = str(value)
        parts[part] = xml_bytes(root)
    buffer = __import__('io').BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def _column_number(column):
    """Converte letras Excel para índice base 1 (A=1, AA=27), sem acessar workbook."""
    return sum((ord(char)-64)*26**index for index, char in enumerate(reversed(column)))


def _column_label(value):
    """Converte índice Excel base 1 para letras (1=A, 27=AA)."""
    result = ''
    while value:
        value, remainder = divmod(value-1, 26)
        result = chr(65+remainder)+result
    return result


def patch_chart(parts, owner, node, patch, suffix):
    """Clona um gráfico por instância e sincroniza caches e XLSX incorporado.

    series aceita name, labels, values, xValues e yValues. Mantém quantidade de
    séries/pontos e a configuração visual original. O clone evita alterar outro
    slide que use o mesmo gráfico/workbook. suffix identifica slide e elemento.
    """
    if set(patch)-{'series', 'xmlPatches'}:
        raise ValueError('chart aceita somente series e xmlPatches')
    reference = node.find('.//c:chart', NS)
    if reference is None:
        raise ValueError('Objeto não é um gráfico')
    rid = reference.get(q('r', 'id'))
    original = relationships(parts, owner)[rid]['target']
    target = f'ppt/charts/config-{suffix}.xml'
    root = parse_xml(parts[original])
    series_nodes = root.findall('.//c:ser', NS)
    configured = patch.get('series', [{} for _ in series_nodes])
    if len(configured) != len(series_nodes):
        raise ValueError('chart.series precisa manter a quantidade de séries')
    updates = []
    for series, changes in zip(series_nodes, configured):
        mapping = {'name': 'c:tx', 'labels': 'c:cat', 'values': 'c:val',
                   'xValues': 'c:xVal', 'yValues': 'c:yVal'}
        if set(changes)-set(mapping):
            raise ValueError(f'Opções de série desconhecidas: {set(changes)-set(mapping)}')
        for key, path in mapping.items():
            if key not in changes:
                continue
            values = [changes[key]] if key == 'name' else changes[key]
            container = series.find(path, NS)
            if container is None:
                raise ValueError(f'Gráfico não possui {key}')
            cache = next((e for e in container.iter() if local(e.tag) in ('strCache', 'numCache', 'numLit', 'strLit')), None)
            if cache is None:
                direct = container.find('c:v', NS)
                if key == 'name' and direct is not None:
                    direct.text = str(values[0])
                    continue
                raise ValueError(f'Cache de gráfico não suportado: {key}')
            points = cache.findall('c:pt', NS)
            if len(points) != len(values):
                raise ValueError('Quantidade de pontos precisa permanecer igual no modo fiel')
            for pt, value in zip(points, values):
                ensure(pt, q('c', 'v')).text = str(value)
            formula = container.find('.//c:f', NS)
            if formula is not None:
                updates.append((formula.text, values))
    xml_operations(root, patch.get('xmlPatches', []), suffix)
    parts[target] = xml_bytes(root)
    original_rels = rel_path(original)
    if original_rels in parts:
        relations = parse_xml(parts[original_rels])
        for relation in relations:
            if relation.get('TargetMode') == 'External':
                continue
            old = resolve_target(original, relation.get('Target'))
            if old.endswith('.xlsx') and updates:
                new = f'ppt/embeddings/config-{suffix}.xlsx'
                parts[new] = workbook_cells(parts[old], updates)
                relation.set('Target', posixpath.relpath(new, posixpath.dirname(target)))
                add_content_type(parts, new, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            else:
                relation.set('Target', posixpath.relpath(old, posixpath.dirname(target)))
        parts[rel_path(target)] = xml_bytes(relations)
    add_content_type(parts, target, 'application/vnd.openxmlformats-officedocument.drawingml.chart+xml')
    replace_relation(parts, owner, rid, target)


def patch_picture(parts, owner, node, filename, suffix):
    """Substitui uma imagem por instância, mantendo crop, efeitos e geometria.

    filename é arquivo local ou {path,fallback}. Para SVG, fallback é PNG criado
    pelo wrapper JavaScript. O pacote mantém o vetor mais PNG de compatibilidade;
    recursos antigos compartilhados não são alterados.
    """
    fallback = filename.get('fallback') if isinstance(filename, dict) else None
    source = (ROOT/(filename['path'] if isinstance(filename, dict) else filename)).resolve()
    extension = source.suffix.lower()
    types = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
             '.svg': 'image/svg+xml', '.gif': 'image/gif'}
    if extension not in types:
        raise ValueError(f'Formato de imagem não suportado: {extension}')
    blip = node.find('.//a:blip', NS)
    if blip is None:
        raise ValueError('Objeto não possui imagem')
    target = f'ppt/media/config-{suffix}{extension}'
    parts[target] = source.read_bytes()
    rid = blip.get(q('r', 'embed'))
    if rid is None:
        raise ValueError('Imagem vinculada externamente: forneça um override XML explícito')
    if extension == '.svg':
        if not fallback:
            raise ValueError('SVG novo requer fallback PNG; gere pela API JavaScript ou forneça {path,fallback}')
        raster = f'ppt/media/config-{suffix}.png'
        parts[raster] = (ROOT/fallback).resolve().read_bytes()
        replace_relation(parts, owner, rid, raster)
        add_content_type(parts, raster, 'image/png')
    else:
        replace_relation(parts, owner, rid, target)
    for child in list(blip):
        if local(child.tag) == 'extLst':
            blip.remove(child)
    if extension == '.svg':
        relations = parse_xml(parts[rel_path(owner)])
        svg_id = 'rIdSvg'+suffix
        relation = ET.SubElement(relations, q('rel', 'Relationship'), Id=svg_id,
            Type=NS['r']+'/image', Target=posixpath.relpath(target, posixpath.dirname(owner)))
        parts[rel_path(owner)] = xml_bytes(relations)
        ext = ET.SubElement(ET.SubElement(blip, q('a', 'extLst')), q('a', 'ext'),
                            uri='{96DAC541-7B7A-43D3-8B79-37D633B846F1}')
        ET.SubElement(ext, q('asvg', 'svgBlip'), {q('r', 'embed'): svg_id})
    add_content_type(parts, target, types[extension])


def xml_operations(root, operations, context):
    """Aplica escape hatch DrawingML com XPath, atributos, texto, remoção ou append.

    root é a parte/objeto proprietário. Cada operação exige path; attributes e
    text editam nós existentes; remove elimina o nó; appendXml insere um fragmento
    completo com namespaces declarados. context aparece nas mensagens de erro.
    Esta API avançada expõe propriedades sem equivalente no PptxGenJS.
    """
    for operation in operations:
        if set(operation)-{'path', 'attributes', 'text', 'remove', 'appendXml'}:
            raise ValueError(f'Operação XML desconhecida: {context}')
        namespaces = {**NAMESPACE_HINTS, **NS}
        targets = root.findall(operation['path'], namespaces)
        if not targets:
            raise ValueError(f'XPath não encontrado em {context}: {operation["path"]}')
        for target in targets:
            for key, value in operation.get('attributes', {}).items():
                if ':' in key and not key.startswith('{'):
                    prefix, name = key.split(':', 1)
                    key = '{'+namespaces[prefix]+'}'+name
                target.set(key, str(value))
            if 'text' in operation:
                target.text = str(operation['text'])
            if 'appendXml' in operation:
                target.append(parse_xml(operation['appendXml'].encode('utf-8')))
            if operation.get('remove'):
                parent = next((p for p in root.iter() if target in list(p)), None)
                if parent is None:
                    raise ValueError('Não é possível remover a raiz de uma parte')
                parent.remove(target)


def apply_element(parts, owner, record, patch, config, slide_size, suffix):
    """Aplica overrides a um objeto nativo sem reconstruir os irmãos.

    Ordem: texto/runs -> estilo -> geometria -> fill/linha -> tabela/gráfico/
    imagem -> XML avançado -> visibilidade. Remover um grupo remove seus filhos.
    Não aceita chaves desconhecidas. xmlPatches permite configurar propriedades
    DrawingML não cobertas pela API amigável, preservando acesso completo.
    """
    allowed = {'text', 'textRuns', 'textReplacements', 'textStyle', 'box', 'localBox',
        'grid', 'fill', 'line', 'rotation', 'visible', 'table', 'chart', 'image',
        'xmlPatches', 'shapeType', 'name'}
    unknown = set(patch)-allowed
    if unknown:
        raise ValueError(f'Opções desconhecidas em {suffix}: {sorted(unknown)}')
    node = record['node']
    if 'text' in patch:
        replace_text(node, patch['text'])
    if 'textRuns' in patch:
        runs = list(node.iter(q('a', 't')))
        for index, value in patch['textRuns'].items():
            runs[int(index)].text = str(value)
    if 'textReplacements' in patch:
        for t in node.iter(q('a', 't')):
            for before, after in patch['textReplacements'].items():
                t.text = (t.text or '').replace(before, str(after))
    if 'textStyle' in patch:
        text_style(node, patch['textStyle'])
    if any(key in patch for key in ('box', 'grid', 'localBox')):
        apply_box(record, patch, config.get('grid', {}), slide_size)
    if 'rotation' in patch:
        materialize_transform(record).set('rot', str(round(patch['rotation']*60000)))
    if any(key in patch for key in ('fill', 'line', 'shapeType')):
        properties = node.find('p:spPr', NS)
        if properties is None:
            raise ValueError('fill/line/shapeType requer uma forma; tabelas usam table.cells')
        if 'fill' in patch:
            set_color(properties, patch['fill'])
        if 'line' in patch:
            line = ensure(properties, q('a', 'ln'))
            if 'color' in patch['line']:
                set_color(line, patch['line']['color'])
            if 'width' in patch['line']:
                line.set('w', str(round(patch['line']['width']*12700)))
        if 'shapeType' in patch:
            for child in list(properties):
                if local(child.tag) in ('custGeom', 'prstGeom'):
                    properties.remove(child)
            geometry = ET.SubElement(properties, q('a', 'prstGeom'), prst=patch['shapeType'])
            ET.SubElement(geometry, q('a', 'avLst'))
    if 'name' in patch:
        next(n for n in node.iter(q('p', 'cNvPr'))).set('name', patch['name'])
    if 'table' in patch:
        patch_table(node, patch['table'])
    if 'chart' in patch:
        patch_chart(parts, owner, node, patch['chart'], suffix)
    if 'image' in patch:
        patch_picture(parts, owner, node, patch['image'], suffix)
    xml_operations(node, patch.get('xmlPatches', []), suffix)
    if patch.get('visible') is False:
        record['parent'].remove(node)


def flow_patches(scene, flow, config, size):
    """Calcula posições de uma coleção em ordem de leitura, sem alterar texto.

    flow define elements (IDs na ordem desejada), region (polegadas), minWidth,
    gap e maxColumns. A quantidade de colunas depende da largura disponível;
    os itens continuam na linha seguinte, da esquerda para a direita. Cada item
    recebe uma caixa de mesmo tamanho. Resize de grupo preserva seu espaço interno.
    """
    if set(flow)-{'elements', 'region', 'minWidth', 'gap', 'maxColumns'}:
        raise ValueError('flow contém opções desconhecidas')
    ids = flow['elements']
    if not ids or any(key not in scene for key in ids):
        raise ValueError('flow.elements precisa referenciar objetos existentes')
    if len(set(ids)) != len(ids):
        raise ValueError('flow.elements contém IDs duplicados')
    if any(scene[key]['parentId'] in ids for key in ids):
        raise ValueError('Não reordene simultaneamente um grupo e seu filho')
    region = flow.get('region', {'x': 0.56, 'y': 1.3, 'w': size['width']-1.12, 'h': size['height']-1.9})
    gap = float(flow.get('gap', 0.12))
    minimum = float(flow.get('minWidth', 2))
    if minimum <= 0 or gap < 0 or min(region['w'], region['h']) <= 0:
        raise ValueError('flow possui dimensões inválidas')
    if int(flow.get('maxColumns', len(ids))) < 1:
        raise ValueError('flow.maxColumns precisa ser positivo')
    columns = max(1, min(len(ids), int(flow.get('maxColumns', len(ids))),
                        int((region['w']+gap)/(minimum+gap))))
    rows = math.ceil(len(ids)/columns)
    w = (region['w']-(columns-1)*gap)/columns
    h = (region['h']-(rows-1)*gap)/rows
    if min(w, h) <= 0:
        raise ValueError('flow não tem área suficiente')
    return {key: {'box': dict(x=region['x']+(i % columns)*(w+gap),
                             y=region['y']+(i//columns)*(h+gap), w=w, h=h)}
            for i, key in enumerate(ids)}


def patch_part(parts, part, patch, config, dimensions, suffix):
    """Aplica configuração a slide/layout/master e serializa somente essa parte.

    element IDs são validados. A cena é recalculada após cada geometria de pai
    para que um override posterior de filho use a transformação atualizada.
    """
    root = parse_xml(parts[part])
    ancestors = ancestors_for(parts, part)
    scene = scene_nodes(root, ancestors)
    elements = copy.deepcopy(patch.get('elements', {}))
    for flow in patch.get('flows', []):
        for key, value in flow_patches(scene, flow, config, dimensions).items():
            elements[key] = {**value, **elements.get(key, {})}
    for key, changes in elements.items():
        scene = scene_nodes(root, ancestors)
        if key not in scene:
            raise ValueError(f'{suffix}: elemento inexistente {key}')
        apply_element(parts, part, scene[key], changes, config, dimensions, suffix+'-'+key)
    if 'background' in patch:
        common = root.find('p:cSld', NS)
        background = common.find('p:bg', NS)
        if background is not None:
            common.remove(background)
        background = ET.Element(q('p', 'bg'))
        properties = ET.SubElement(background, q('p', 'bgPr'))
        set_color(properties, patch['background'])
        common.insert(0, background)
    if 'hidden' in patch:
        root.set('show', '0' if patch['hidden'] else '1')
    parts[part] = xml_bytes(root)


def apply_theme(parts, theme):
    """Aplica tokens apenas quando solicitados, deixando o baseline intacto.

    colorMap/fontMap substituem valores exatos em todas as partes XML. colors
    aceita primary/surface/paper/text; fonts aceita body/heading. Não recolore
    arquivos de imagem: logos oficiais e artwork incorporado permanecem originais.
    """
    color_map = dict(theme.get('colorMap', {}))
    font_map = dict(theme.get('fontMap', {}))
    base_colors = {'primary': 'EC111A', 'surface': 'F5EFE8', 'paper': 'FFFFFF', 'text': '1E1117'}
    for key, color in theme.get('colors', {}).items():
        if key not in base_colors:
            raise ValueError(f'Token de cor desconhecido: {key}; use colorMap para valores específicos')
        if color.upper() != base_colors[key]:
            color_map[base_colors[key]] = color.upper()
    for key, font in theme.get('fonts', {}).items():
        old = {'body': 'Scotia', 'heading': 'Scotia Headline'}[key]
        if font != old:
            font_map[old] = font
    for part, payload in list(parts.items()):
        if not part.endswith('.xml') or not (color_map or font_map):
            continue
        # Lexical substitutions retain mc:Ignorable prefixes and every unrelated byte.
        value = payload.decode('utf-8')
        for before, after in color_map.items():
            if not re.fullmatch(r'[A-Fa-f0-9]{6}', after):
                raise ValueError('Cor de token inválida')
            value = re.sub(r'(<(?:\w+:)?srgbClr\b[^>]*\bval=")'+re.escape(before)+r'(")',
                           lambda m: m.group(1)+after+m.group(2), value, flags=re.I)
        for before, after in font_map.items():
            if any(ch in after for ch in '<>&"'):
                raise ValueError('Nome de fonte contém caracteres XML inválidos')
            value = value.replace(f'typeface="{before}"', f'typeface="{after}"')
        if value.encode('utf-8') != payload:
            parts[part] = value.encode('utf-8')


def merge_additions(parts, scaffold_parts, selection):
    """Importa objetos novos efetivamente gerados pelo PptxGenJS.

    Aceita texto, formas, tabelas e gráficos com suas dependências OPC. IDs são realocados acima
    do maior ID original. Objetos nomeados custom.* são os únicos importados;
    títulos auxiliares do scaffold não substituem os objetos de referência.
    """
    added = 0
    imported = {}
    content_types = parse_xml(parts['[Content_Types].xml'])
    source_types = parse_xml(scaffold_parts['[Content_Types].xml'])

    def import_resource(source):
        """Copia uma dependência e sua árvore de relações com nomes privados.

        source é uma parte do scaffold; imported evita cópias duplicadas/ciclos.
        Workbooks, imagens e estilos dos gráficos recebem o mesmo tratamento.
        """
        if source in imported:
            return imported[source]
        target = posixpath.join(posixpath.dirname(source), 'generated-'+posixpath.basename(source))
        while target in parts:
            target = posixpath.join(posixpath.dirname(target), 'generated-'+posixpath.basename(target))
        imported[source] = target
        parts[target] = scaffold_parts[source]
        override = next((n for n in source_types if n.get('PartName') == '/'+source), None)
        if override is not None:
            item = copy.deepcopy(override)
            item.set('PartName', '/'+target)
            content_types.append(item)
        extension = target.rsplit('.', 1)[-1]
        if not any(n.get('Extension') == extension for n in content_types):
            default = next((n for n in source_types if n.get('Extension') == extension), None)
            if default is not None:
                content_types.append(copy.deepcopy(default))
        relationship_part = rel_path(source)
        if relationship_part in scaffold_parts:
            relroot = parse_xml(scaffold_parts[relationship_part])
            for rel in relroot:
                if rel.get('TargetMode') != 'External':
                    dependency = import_resource(resolve_target(source, rel.get('Target')))
                    rel.set('Target', posixpath.relpath(dependency, posixpath.dirname(target)))
            parts[rel_path(target)] = xml_bytes(relroot)
        return target

    for index, number in enumerate(selection, 1):
        generated = parse_xml(scaffold_parts[f'ppt/slides/slide{index}.xml'])
        extras = [n for n in drawable_children(generated.find('p:cSld/p:spTree', NS))
                  if identity(n) and identity(n)['name'].startswith('custom.')]
        if not extras:
            continue
        part = f'ppt/slides/slide{number}.xml'
        root = parse_xml(parts[part])
        tree = root.find('p:cSld/p:spTree', NS)
        relroot = parse_xml(parts[rel_path(part)])
        generated_owner = f'ppt/slides/slide{index}.xml'
        generated_rels = parse_xml(scaffold_parts[rel_path(generated_owner)])
        used_ids = {r.get('Id') for r in relroot}
        remapped = {}
        last = max(int(n.get('id')) for n in root.iter(q('p', 'cNvPr')))
        for extra in extras:
            for element in extra.iter():
                for attr, value in list(element.attrib.items()):
                    if not attr.startswith('{'+NS['r']+'}'):
                        continue
                    if value not in remapped:
                        relation = copy.deepcopy(next(r for r in generated_rels if r.get('Id') == value))
                        rid = 'rIdGenerated'+str(len(used_ids)+1)
                        while rid in used_ids:
                            rid += 'x'
                        used_ids.add(rid)
                        relation.set('Id', rid)
                        if relation.get('TargetMode') != 'External':
                            dependency = import_resource(resolve_target(generated_owner, relation.get('Target')))
                            relation.set('Target', posixpath.relpath(dependency, posixpath.dirname(part)))
                        relroot.append(relation)
                        remapped[value] = rid
                    element.set(attr, remapped[value])
            for prop in extra.iter(q('p', 'cNvPr')):
                last += 1
                prop.set('id', str(last))
            tree.append(extra)
            added += 1
        parts[part] = xml_bytes(root)
        parts[rel_path(part)] = xml_bytes(relroot)
    if imported:
        parts['[Content_Types].xml'] = xml_bytes(content_types)
    return added


def validate_config(config):
    """Rejeita opções desconhecidas antes de escrever qualquer saída.

    O modo fiel tem seu próprio contrato. As opções dos sete templates adaptativos
    continuam disponíveis pelo modo responsive, evitando overrides silenciosos.
    """
    allowed = {'mode', 'grid', 'theme', 'slides', 'templates', 'masters', 'elements',
               'selection', 'additions', 'showHidden', 'source', 'slide', 'nativeParts', 'quality'}
    if set(config)-allowed:
        raise ValueError(f'Chaves desconhecidas no modo fidelity: {sorted(set(config)-allowed)}')
    for key in ('columns', 'rows'):
        value = config.get('grid', {}).get(key, 14 if key == 'columns' else 9)
        if not isinstance(value, int) or value < 1:
            raise ValueError(f'grid.{key} precisa ser inteiro positivo')
    for number, patch in config.get('slides', {}).items():
        if set(patch)-{'elements', 'flows', 'background', 'hidden'}:
            raise ValueError(f'Slide {number}: opções desconhecidas')
    for group in ('templates', 'masters'):
        for key, patch in config.get(group, {}).items():
            if set(patch)-{'elements', 'flows', 'background'}:
                raise ValueError(f'{group}.{key}: opções desconhecidas')


def build_native(source, scaffold, config, output):
    """Monta o PPTX fiel e produz um relatório verificável.

    source é a referência imutável; scaffold é o PPTX criado pelo PptxGenJS;
    config contém overrides explícitos; output é o arquivo de destino. O pacote
    original é preservado e recebe metadados e adições do scaffold. O relatório
    distingue igualdade dos bytes visuais de qualquer mudança configurada.
    """
    validate_config(config)
    source, output = Path(source), Path(output)
    if output.resolve() == source.resolve():
        raise ValueError('A saída não pode sobrescrever o PPTX de referência')
    original = read_parts(source)
    parts = dict(original)
    generated = read_parts(scaffold)
    catalog = source_catalog(source)
    dimensions = catalog['slide']
    requested_size = config.get('slide', dimensions)
    if requested_size != dimensions:
        raise ValueError('Modo fiel preserva o canvas original 16:9. Use grid/box ou modo responsive para redimensionar.')
    selection = config.get('selection', list(range(1, len(catalog['slides'])+1)))
    if not selection or len(selection) != len(set(selection)) or any(n not in range(1, len(catalog['slides'])+1) for n in selection):
        raise ValueError('selection deve conter números de slides existentes, sem repetições')
    generated_count = sum(bool(re.fullmatch(r'ppt/slides/slide\d+\.xml', name)) for name in generated)
    if generated_count != len(selection):
        raise ValueError('Quantidade de slides do scaffold diverge da seleção')
    apply_theme(parts, config.get('theme', {}))
    for group, source_group in [('masters', 'masters'), ('templates', 'layouts')]:
        for key, patch in config.get(group, {}).items():
            if key not in catalog[source_group]:
                raise ValueError(f'{group} não encontrado: {key}')
            patch_part(parts, catalog[source_group][key]['part'], patch, config, dimensions, key)
    slide_patches = copy.deepcopy(config.get('slides', {}))
    for key, value in config.get('elements', {}).items():
        number, ident = key.split('.', 1)
        slide_patches.setdefault(number, {}).setdefault('elements', {})[ident] = value
    if config.get('showHidden'):
        for slide in catalog['slides']:
            if slide['hidden']:
                slide_patches.setdefault(str(slide['number']), {})['hidden'] = False
    for number, patch in slide_patches.items():
        if not number.isdigit() or int(number) not in range(1, len(catalog['slides'])+1):
            raise ValueError(f'Slide inexistente: {number}')
        patch_part(parts, f'ppt/slides/slide{number}.xml', patch, config, dimensions, 's'+number)
    for name, operations in config.get('nativeParts', {}).items():
        if name not in parts or not name.endswith(('.xml', '.rels')):
            raise ValueError(f'Parte XML inexistente: {name}')
        root = parse_xml(parts[name])
        xml_operations(root, operations, name)
        parts[name] = xml_bytes(root)
    added = merge_additions(parts, generated, selection)
    quality_report = None
    if selection != list(range(1, len(catalog['slides'])+1)):
        root = parse_xml(parts['ppt/presentation.xml'])
        children = root.find('p:sldIdLst', NS)
        entries = list(children)
        for entry in entries:
            children.remove(entry)
        for number in selection:
            children.append(entries[number-1])
        # Seções de navegação com slides omitidos não devem apontar para páginas ausentes.
        for parent in root.iter():
            for child in list(parent):
                if local(child.tag) == 'sectionLst':
                    parent.remove(child)
        parts['ppt/presentation.xml'] = xml_bytes(root)
        if 'docProps/app.xml' in parts:
            app = parse_xml(parts['docProps/app.xml'])
            for item in app.iter():
                if local(item.tag) == 'Slides':
                    item.text = str(len(selection))
            parts['docProps/app.xml'] = xml_bytes(app)
    if config.get('quality'):
        from quality_deck import normalize_package
        quality_report = normalize_package(parts, config['quality'], dimensions, selection)
    # Core properties prove the generated package participated; visual parts remain untouched.
    parts['docProps/core.xml'] = generated['docProps/core.xml']
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.writing.pptx')
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, payload in parts.items():
                archive.writestr(name, payload)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    changed = [name for name in parts if original.get(name) != parts[name]]
    nonvisual = {'docProps/core.xml'}
    report = {'mode': 'fidelity', 'sourceFile': str(source.resolve()), 'sourceSha256': catalog['sourceSha256'],
        'outputSha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'slideSize': dimensions, 'grid': config.get('grid', {'columns': 14, 'rows': 9}),
        'selection': selection, 'counts': {**catalog['counts'], 'outputSlides': len(selection), 'additions': added},
        'changedParts': changed, 'unchangedSourceParts': len(set(parts)&set(original))-len([n for n in changed if n in original]),
        'baselineVisualPartsByteIdentical': not (set(changed)-nonvisual),
        'fonts': 'Original font declarations preserved unless configured. Fonts are not embedded in the source.',
        'scaffold': {'library': 'PptxGenJS', 'slides': generated_count},
        'slides': [{'sourceNumber': n, 'part': f'ppt/slides/slide{n}.xml',
                    'elements': describe_scene(parts, f'ppt/slides/slide{n}.xml', dimensions)} for n in selection]}
    if quality_report is not None:
        report['quality'] = quality_report
        report['fonts'] = 'Explicit '+config['quality']['font']+' typography; fonts are not embedded.'
        report['counts']['outputSlides'] += len(quality_report['continuations'])
        for continuation in quality_report['continuations']:
            position = next(i for i, slide in enumerate(report['slides']) if slide['sourceNumber'] == continuation['sourceNumber'])
            report['slides'].insert(position+continuation['page']-1,
              {**continuation, 'elements': describe_scene(parts, continuation['part'], dimensions)})
    output.with_suffix('.layout.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main():
    """Executa catalog/build pela CLI; falhas interrompem o build com contexto."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['catalog', 'build'])
    parser.add_argument('--source', default=str(SOURCE))
    parser.add_argument('--scaffold')
    parser.add_argument('--config')
    parser.add_argument('--catalog-output', default=str(ROOT/'data/catalog.json'))
    parser.add_argument('--output', default=str(ROOT/'output/recreated-slides.pptx'))
    args = parser.parse_args()
    if args.command == 'catalog':
        result = source_catalog(Path(args.source), Path(args.catalog_output))
        print(json.dumps(result['counts']))
    else:
        config = json.loads(Path(args.config).read_text()) if args.config else {}
        result = build_native(args.source, args.scaffold, config, args.output)
        print(json.dumps({'slides': result['counts']['outputSlides'],
            'baselineVisualPartsByteIdentical': result['baselineVisualPartsByteIdentical'],
            'changedParts': len(result['changedParts'])}))


if __name__ == '__main__':
    main()
