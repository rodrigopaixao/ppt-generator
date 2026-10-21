"""Expose rendered chart labels as editable text while preserving native chart data."""
import copy
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import native_deck as native

NS = native.NS


def chart_frames(parts, scene):
    """Resolve visible chart instances with stable owner IDs and native geometry."""
    from editor_scene import layer_roots, parent_ids
    result = []
    for layer, (part, root) in layer_roots(parts, scene['part']).items():
        if layer != 'slide' and layer_roots(parts, scene['part'])['slide'][1].get('showMasterSp') == '0':
            continue
        records = native.scene_nodes(root, native.ancestors_for(parts, part))
        for item in native.describe_scene(parts, part, scene):
            if item['kind'] != 'chart' or not item.get('box') or item['hidden']:
                continue
            if any(records[parent]['hidden'] for parent in parent_ids(records[item['id']], records)):
                continue
            owner = item['name'].removeprefix(str(scene['number']) + '.') if item['name'].startswith(str(scene['number']) + '.') else item['id']
            if layer != 'slide':
                owner = layer + '.' + owner
            result.append({**item, 'ownerId': owner, 'layer': layer, 'part': part})
    return result


def write_package(parts, destination):
    """Write a complete OPC archive into a private temporary or output file."""
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, payload in parts.items():
            archive.writestr(name, payload)


def render_pdf(parts, scene, folder):
    """Render a single visible slide with an isolated LibreOffice profile."""
    soffice = os.environ.get('SOFFICE_BIN') or shutil.which('soffice')
    if not soffice:
        raise RuntimeError('Install LibreOffice to edit chart text')
    presentation = native.parse_xml(parts['ppt/presentation.xml'])
    rels = native.relationships(parts, 'ppt/presentation.xml')
    ids = presentation.find('p:sldIdLst', NS)
    for sid in list(ids):
        if rels[sid.get(native.q('r', 'id'))]['target'] != scene['part']:
            ids.remove(sid)
    parts['ppt/presentation.xml'] = native.xml_bytes(presentation)
    root = native.parse_xml(parts[scene['part']])
    root.attrib.pop('show', None)
    parts[scene['part']] = native.xml_bytes(root)
    deck = folder / 'chart-text.pptx'
    write_package(parts, deck)
    subprocess.run([soffice, '-env:UserInstallation=' + (folder / 'profile').as_uri(),
                    '--headless', '--convert-to', 'pdf', '--outdir', str(folder), str(deck)],
                   check=True, capture_output=True, timeout=70)
    return deck.with_suffix('.pdf')


def chart_only(parts, scene, frames):
    """Keep chart instances and their parent groups, excluding unrelated text/images."""
    from editor_scene import layer_roots, parent_ids
    for layer, (part, root) in layer_roots(parts, scene['part']).items():
        records = native.scene_nodes(root, native.ancestors_for(parts, part))
        keep = set()
        for frame in frames:
            if frame['layer'] == layer:
                keep.add(frame['id'])
                keep.update(parent_ids(records[frame['id']], records))
        for ident, record in records.items():
            if ident not in keep and record['node'] in list(record['parent']):
                record['parent'].remove(record['node'])
        parts[part] = native.xml_bytes(root)
    return parts


def font_style(word):
    """Translate PDF font/color attributes to the browser's supported typography."""
    font = re.sub(r'^[A-Z]{6}\+', '', word.get('fontname', 'Arial'))
    bold = bool(re.search(r'Bold|Black|Heavy|Demi', font, re.I))
    italic = bool(re.search(r'Italic|Oblique', font, re.I))
    family = re.sub(r'[-,]?(Bold|Italic|Oblique|Regular|MT|PSMT|PS|Roman)', '', font, flags=re.I).strip('- ,') or 'Arial'
    family = {'LinuxLibertineG': 'Linux Libertine G', 'LinuxBiolinumG': 'Linux Biolinum G',
              'LiberationSans': 'Liberation Sans', 'LiberationSerif': 'Liberation Serif',
              'LiberationMono': 'Liberation Mono'}.get(family, family)
    color = word.get('non_stroking_color')
    if isinstance(color, (int, float)):
        color = [color] * 3
    if not isinstance(color, (tuple, list)) or len(color) not in (3, 4):
        color = [0, 0, 0]
    if len(color) == 4:
        cyan, magenta, yellow, black = color
        color = [(1-cyan)*(1-black), (1-magenta)*(1-black), (1-yellow)*(1-black)]
    return {'fontFamily': family, 'fontSize': float(word.get('size', 10)),
            'color': '#' + ''.join(f'{max(0, min(255, round(c*255))):02x}' for c in color),
            'bold': bold, 'italic': italic, 'align': 'left', 'vertical': 'top',
            'margins': [0, 0, 0, 0], 'lineHeight': 1.0}


def rendered_words(page):
    """Extract upright and rotated labels with consistent font sizes and reading order."""
    import pdfplumber
    groups = {}
    for char in page.chars:
        char = dict(char)
        matrix = char.get('matrix', (1, 0, 0, 1, 0, 0))
        angle = round(math.degrees(math.atan2(matrix[1], matrix[0])))
        if not char.get('upright', True):
            # PDFMiner reports rotated glyph advances as size; the perpendicular
            # glyph width retains the font's actual point size.
            char['size'] = round(char['width'], 3)
        groups.setdefault(angle, []).append(char)
    result = []
    for angle, chars in groups.items():
        options = {'char_dir_rotated': 'btt' if angle >= 0 else 'ttb', 'line_dir_rotated': 'ltr'}
        if abs(angle) > 135:
            options['char_dir'] = 'rtl'
        result.extend(pdfplumber.utils.extract_words(chars, keep_blank_chars=True, x_tolerance=2, y_tolerance=2,
            extra_attrs=['fontname', 'size', 'non_stroking_color', 'upright'], return_chars=True, **options))
    return result


def extract(source, scene):
    """Measure actual chart labels from PDF text, including computed axis ticks.

    Geometry comes from the same Office renderer used for the preview. Labels
    become literal display text; the chart's cached data and workbook stay native.
    """
    import pdfplumber
    parts = native.read_parts(source)
    frames = chart_frames(parts, scene)
    if not frames:
        return []
    with tempfile.TemporaryDirectory(prefix='pptx-chart-text-') as directory:
        pdf = render_pdf(chart_only(parts, scene, frames), scene, Path(directory))
        with pdfplumber.open(pdf) as document:
            page = document.pages[0]
            words = rendered_words(page)
            result = []
            # Assign each rendered word to its closest containing chart. Each
            # chart is rendered without other slide objects, avoiding title collisions.
            grouped = {frame['ownerId']: [] for frame in frames}
            for word in words:
                cx, cy = (word['x0']+word['x1'])/144, (word['top']+word['bottom'])/144
                candidates = [frame for frame in frames if frame['box']['x']-0.03 <= cx <= frame['box']['x']+frame['box']['w']+0.03
                              and frame['box']['y']-0.03 <= cy <= frame['box']['y']+frame['box']['h']+0.03]
                if candidates and word['text'].strip():
                    frame = min(candidates, key=lambda frame: frame['box']['w']*frame['box']['h'])
                    grouped[frame['ownerId']].append(word)
            for frame in frames:
                words = sorted(grouped[frame['ownerId']], key=lambda word: (round(word['top'], 2), word['x0']))
                for index, word in enumerate(words):
                    value = word['text'].strip()
                    style = font_style(word)
                    ident = f'{frame["ownerId"]}/chart-text/{index}'
                    box = {'x': word['x0']/72, 'y': word['top']/72,
                           'w': max((word['x1']-word['x0'])/72+0.025, 0.05),
                           'h': max((word['bottom']-word['top'])/72+0.025, style['fontSize']/72*1.15)}
                    rotation = 0
                    if word.get('chars'):
                        matrix = word['chars'][0].get('matrix', (1, 0, 0, 1, 0, 0))
                        rotation = -math.degrees(math.atan2(matrix[1], matrix[0]))
                        cx, cy = box['x']+box['w']/2, box['y']+box['h']/2
                        if abs(abs(rotation) - 90) < 1:
                            box['w'], box['h'] = box['h'], box['w']
                        box['x'], box['y'] = cx-box['w']/2, cy-box['h']/2
                    result.append({'id': ident, 'nativeId': frame['id'], 'name': f'{frame["name"]}, label {index+1}',
                        'text': value, 'originalText': value, 'box': box, 'rotation': rotation,
                        'role': 'paragraph', 'editable': True, 'style': style,
                        'target': {'kind': 'chartText', 'ownerId': frame['ownerId'], 'nativeId': frame['id'],
                                   'layer': frame['layer'], 'chartBox': frame['box']}})
            return result


def transparent_text(chart):
    """Hide native chart glyphs without deleting labels or changing plot layout."""
    # Establish a chart-wide default and override explicit run/default colors.
    default = chart.find('c:txPr', NS)
    if default is None:
        default = ET.Element(native.q('c', 'txPr'))
        # txPr precedes externalData, printSettings and extensions in CT_ChartSpace.
        insertion = next((i for i, child in enumerate(chart) if native.local(child.tag) in ('externalData', 'printSettings', 'userShapes', 'extLst')), len(chart))
        chart.insert(insertion, default)
        ET.SubElement(default, native.q('a', 'bodyPr'))
        ET.SubElement(default, native.q('a', 'lstStyle'))
        paragraph = ET.SubElement(default, native.q('a', 'p'))
        properties = ET.SubElement(paragraph, native.q('a', 'pPr'))
        ET.SubElement(properties, native.q('a', 'defRPr'))
    properties = [node for node in chart.iter() if native.local(node.tag) in ('rPr', 'defRPr', 'endParaRPr')]
    for prop in properties:
        for child in list(prop):
            if native.local(child.tag) in ('solidFill', 'noFill', 'gradFill', 'pattFill', 'blipFill', 'grpFill'):
                prop.remove(child)
        fill = ET.Element(native.q('a', 'solidFill'))
        color = ET.SubElement(fill, native.q('a', 'srgbClr'), {'val': '000000'})
        ET.SubElement(color, native.q('a', 'alpha'), {'val': '0'})
        position = 1 if len(prop) and native.local(prop[0].tag) == 'ln' else 0
        prop.insert(position, fill)


def hide_chart(parts, part, node, suffix):
    """Clone and mute one chart, retaining series, embedded workbooks and legend keys."""
    native.patch_chart(parts, part, node, {}, suffix)
    reference = node.find('.//c:chart', NS)
    chart_part = native.relationships(parts, part)[reference.get(native.q('r', 'id'))]['target']
    chart = native.parse_xml(parts[chart_part])
    transparent_text(chart)
    parts[chart_part] = native.xml_bytes(chart)


def project_element(element, frame):
    """Move a measured label with its chart when a responsive template reflows."""
    result = copy.deepcopy(element)
    before, after = element['target']['chartBox'], frame['box']
    sx, sy = after['w']/(before['w'] or 1), after['h']/(before['h'] or 1)
    box = result['box']
    box.update(x=after['x']+(box['x']-before['x'])*sx, y=after['y']+(box['y']-before['y'])*sy,
               w=box['w']*sx, h=box['h']*sy)
    result['style']['fontSize'] *= min(sx, sy)
    return result


def label_shape(element, value, ident):
    """Create native PowerPoint text for a measured literal chart label."""
    box, style = element['box'], element['style']
    node = ET.Element(native.q('p', 'sp'))
    nonvisual = ET.SubElement(node, native.q('p', 'nvSpPr'))
    ET.SubElement(nonvisual, native.q('p', 'cNvPr'), {'id': str(ident), 'name': 'editor-chart:' + element['id']})
    ET.SubElement(nonvisual, native.q('p', 'cNvSpPr'), {'txBox': '1'})
    ET.SubElement(nonvisual, native.q('p', 'nvPr'))
    props = ET.SubElement(node, native.q('p', 'spPr'))
    transform = ET.SubElement(props, native.q('a', 'xfrm'), {'rot': str(round(element.get('rotation', 0)*60000))})
    ET.SubElement(transform, native.q('a', 'off'), {'x': str(round(box['x']*native.EMU)), 'y': str(round(box['y']*native.EMU))})
    ET.SubElement(transform, native.q('a', 'ext'), {'cx': str(round(box['w']*native.EMU)), 'cy': str(round(box['h']*native.EMU))})
    geometry = ET.SubElement(props, native.q('a', 'prstGeom'), {'prst': 'rect'})
    ET.SubElement(geometry, native.q('a', 'avLst'))
    ET.SubElement(props, native.q('a', 'noFill'))
    ET.SubElement(ET.SubElement(props, native.q('a', 'ln')), native.q('a', 'noFill'))
    body = ET.SubElement(node, native.q('p', 'txBody'))
    ET.SubElement(body, native.q('a', 'bodyPr'), {'wrap': 'none', 'lIns': '0', 'rIns': '0', 'tIns': '0', 'bIns': '0', 'anchor': 't'})
    ET.SubElement(body, native.q('a', 'lstStyle'))
    for line in value.split('\n'):
        paragraph = ET.SubElement(body, native.q('a', 'p'))
        paragraph_props = ET.SubElement(paragraph, native.q('a', 'pPr'), {'algn': 'l'})
        ET.SubElement(paragraph_props, native.q('a', 'buNone'))
        run = ET.SubElement(paragraph, native.q('a', 'r'))
        prop = ET.SubElement(run, native.q('a', 'rPr'), {'sz': str(round(style['fontSize']*100)), 'b': '1' if style['bold'] else '0', 'i': '1' if style['italic'] else '0'})
        ET.SubElement(ET.SubElement(prop, native.q('a', 'solidFill')), native.q('a', 'srgbClr'), {'val': style['color'].lstrip('#')})
        ET.SubElement(prop, native.q('a', 'latin'), {'typeface': style['fontFamily']})
        ET.SubElement(run, native.q('a', 't')).text = line
    return node


def materialize(parts, scene, elements, overrides):
    """Isolate edited charts and add editable literal labels without changing data."""
    from editor_scene import layer_roots, privatize_ancestors
    frames = chart_frames(parts, scene)
    edited_owners = {element['target']['ownerId'] for element in elements if f'{scene["number"]}.{element["id"]}' in overrides}
    if any(frame['layer'] != 'slide' and frame['ownerId'] in edited_owners for frame in frames):
        if not all(Path(part).name.startswith('editor-') for part, _ in native.ancestors_for(parts, scene['part'])):
            privatize_ancestors(parts, scene['part'])
        frames = chart_frames(parts, scene)
    layers = layer_roots(parts, scene['part'])
    for frame in frames:
        labels = [element for element in elements if element['target']['ownerId'] == frame['ownerId']]
        if not any(f'{scene["number"]}.{label["id"]}' in overrides for label in labels):
            continue
        part, root = layers[frame['layer']]
        record = native.scene_nodes(root, native.ancestors_for(parts, part))[frame['id']]
        hide_chart(parts, part, record['node'], f'editor-{scene["number"]}-{frame["layer"]}-{frame["id"]}')
        # Add the overlay to the slide root in slide coordinates, even for a grouped chart.
        slide_root = layers['slide'][1]
        tree = slide_root.find('p:cSld/p:spTree', NS)
        next_id = max(int(node.get('id')) for node in slide_root.iter(native.q('p', 'cNvPr'))) + 1
        for label in labels:
            value = overrides.get(f'{scene["number"]}.{label["id"]}', label['originalText'])
            tree.append(label_shape(project_element(label, frame), value, next_id))
            next_id += 1
        parts[part] = native.xml_bytes(root)
        parts[scene['part']] = native.xml_bytes(slide_root)
