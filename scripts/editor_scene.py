"""Extract editable DrawingML text and render text-free slide backgrounds."""
import copy
import math
import posixpath
import hashlib
import xml.etree.ElementTree as ET
import argparse
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

import native_deck as native
from editor_text import text_body, body_text, edit_body
import editor_chart

NS = native.NS


def first(nodes, selector):
    """Return the first matching child across ordered inheritance layers."""
    return next((found for n in nodes if n is not None
                 for found in [n.find(selector, NS)] if found is not None), None)


def text_layers(node, ancestors):
    """Collect paragraph defaults from slide, placeholders and master styles."""
    nodes = [node] + [native.inherited_node(node, [ancestor])[0] for ancestor in ancestors]
    ph = native.placeholder_of(node) or {}
    style = 'titleStyle' if ph.get('type') in ('title', 'ctrTitle') else 'bodyStyle' if ph.get('type') == 'body' else 'otherStyle'
    paragraphs = []
    for n in nodes:
        if n is not None:
            paragraphs.extend([n.find('p:txBody/a:p/a:pPr', NS), n.find('p:txBody/a:lstStyle/a:lvl1pPr', NS)])
    paragraphs.extend(root.find(f'p:txStyles/p:{style}/a:lvl1pPr', NS) for _, root in ancestors)
    return nodes, [p for p in paragraphs if p is not None]


def theme_context(parts, part, ancestors):
    """Resolve the owning theme's Latin fonts, palette and master color map."""
    context = {'colors': {}, 'fonts': {}, 'mapping': {}}
    owners = [part] + [name for name, _ in ancestors]
    for owner in owners:
        theme_part = next((r['target'] for r in native.relationships(parts, owner).values() if r['type'].endswith('/theme')), None)
        if theme_part:
            root = native.parse_xml(parts[theme_part])
            colors = root.find('a:themeElements/a:clrScheme', NS)
            for entry in colors if colors is not None else []:
                color = next(iter(entry), None)
                if color is not None:
                    context['colors'][native.local(entry.tag)] = color.get('val') if native.local(color.tag) == 'srgbClr' else color.get('lastClr', '000000')
            for key, kind in [('+mj-lt', 'majorFont'), ('+mn-lt', 'minorFont')]:
                font = root.find(f'a:themeElements/a:fontScheme/a:{kind}/a:latin', NS)
                if font is not None:
                    context['fonts'][key] = font.get('typeface', 'Arial')
            break
    for _, root in reversed(ancestors):
        mapping = root.find('p:clrMap', NS)
        if mapping is not None:
            context['mapping'].update(mapping.attrib)
    return context


def style_for(node, ancestors, typography, theme):
    """Resolve browser-supported text properties without rewriting DrawingML."""
    nodes, paragraphs = text_layers(node, ancestors)
    run = node.find('p:txBody/a:p/a:r/a:rPr', NS)
    if run is None:
        run = node.find('p:txBody/a:p/a:fld/a:rPr', NS)
    properties = ([run] if run is not None else []) + [p.find('a:defRPr', NS) for p in paragraphs]
    properties = [p for p in properties if p is not None]
    attrs = {}
    for prop in reversed(properties):
        attrs.update(prop.attrib)
    font = first(properties, 'a:latin')
    font_name = font.get('typeface') if font is not None else 'Arial'
    color = next((p.find('a:solidFill', NS) for p in properties if p.find('a:solidFill', NS) is not None), None)
    color_value = '202124'
    if color is not None:
        rgb, scheme = color.find('a:srgbClr', NS), color.find('a:schemeClr', NS)
        if rgb is not None:
            color_value = rgb.get('val')
        elif scheme is not None:
            key = scheme.get('val')
            color_value = theme['colors'].get(theme['mapping'].get(key, key), '202124')
    body_attrs = {}
    for n in reversed(nodes):
        body = n.find('p:txBody/a:bodyPr', NS) if n is not None else None
        if body is not None:
            body_attrs.update(body.attrib)
    paragraph_attrs = {}
    for p in reversed(paragraphs):
        paragraph_attrs.update(p.attrib)
    line = first(paragraphs, 'a:lnSpc/a:spcPct')
    return {
        'fontFamily': theme['fonts'].get(font_name, font_name),
        'fontSize': float(attrs.get('sz', ((typography or {}).get('size') or 12) * 100)) / 100,
        'color': '#' + color_value,
        'bold': attrs.get('b') == '1', 'italic': attrs.get('i') == '1',
        'underline': attrs.get('u', 'none') != 'none', 'strike': attrs.get('strike', 'noStrike') != 'noStrike',
        'baseline': float(attrs.get('baseline', 0)) / 1000,
        'align': {'ctr': 'center', 'r': 'right', 'just': 'justify'}.get(paragraph_attrs.get('algn'), 'left'),
        'lineHeight': int(line.get('val')) / 100000 if line is not None else 1.1,
        'vertical': {'ctr': 'middle', 'b': 'bottom'}.get(body_attrs.get('anchor'), 'top'),
        'margins': [float(body_attrs.get(k, v)) / native.EMU
                    for k, v in [('tIns', 45720), ('rIns', 91440), ('bIns', 45720), ('lIns', 91440)]],
    }


def simple_text(node, record, ancestors=()):
    """Allow every visible DrawingML text body, including formatted text and fields."""
    return text_body(node) is not None and not record['hidden']


def rich_paragraphs(node, ancestors, theme):
    """Resolve each paragraph and run independently for the browser preview."""
    body = text_body(node)
    output = []
    for paragraph in body.findall('a:p', NS):
        proxy = copy.deepcopy(node)
        existing = text_body(proxy)
        for child in list(existing):
            if native.local(child.tag) == 'p':
                existing.remove(child)
        existing.append(copy.deepcopy(paragraph))
        style = style_for(proxy, ancestors, None, theme)
        props = paragraph.find('a:pPr', NS)
        _, layers = text_layers(proxy, ancestors)
        marker = next((child for layer in layers for child in layer if native.local(child.tag) in ('buNone', 'buChar', 'buAutoNum', 'buBlip')), None)
        bullet = marker if marker is not None and native.local(marker.tag) == 'buChar' else None
        auto = marker if marker is not None and native.local(marker.tag) == 'buAutoNum' else None
        entry = {'style': style, 'runs': []}
        if bullet is not None:
            entry['bullet'] = bullet.get('char', '•')
        elif auto is not None:
            entry['bullet'] = str(len(output) + 1) + '.'
        if props is not None:
            entry['marginLeft'] = float(props.get('marL', 0)) / native.EMU
            entry['indent'] = float(props.get('indent', 0)) / native.EMU
        for child in paragraph:
            kind = native.local(child.tag)
            if kind not in ('r', 'fld', 'br'):
                continue
            run_proxy = copy.deepcopy(proxy)
            run_paragraph = text_body(run_proxy).find('a:p', NS)
            for item in list(run_paragraph):
                if native.local(item.tag) in ('r', 'fld', 'br'):
                    run_paragraph.remove(item)
            run = copy.deepcopy(child)
            run.tag = native.q('a', 'r')
            run_paragraph.append(run)
            entry['runs'].append({'text': '\n' if kind == 'br' else ''.join(t.text or '' for t in child.iter(native.q('a', 't'))),
                                  'style': style_for(run_proxy, ancestors, None, theme)})
        output.append(entry)
    return output


def cell_proxy(cell):
    """Present table-cell typography through the same inheritance resolver as shapes."""
    proxy = ET.Element(native.q('p', 'sp'))
    body = copy.deepcopy(cell.find('a:txBody', NS))
    body.tag = native.q('p', 'txBody')
    props = cell.find('a:tcPr', NS)
    body_props = body.find('a:bodyPr', NS)
    if props is not None and body_props is not None:
        for key, mapped in [('marT', 'tIns'), ('marR', 'rIns'), ('marB', 'bIns'), ('marL', 'lIns'), ('anchor', 'anchor')]:
            if props.get(key) is not None:
                body_props.set(mapped, props.get(key))
    proxy.append(body)
    return proxy


def text_geometry(record, offset=(0, 0), extent=None):
    """Map a local text rectangle through object and nested-group transforms."""
    xf = record['effectiveTransform']
    x, y, w, h = native.transform_values(xf)
    angle = math.radians(float(xf.get('rot', 0)) / 60000)
    fx = -1 if xf.get('flipH') == '1' else 1
    fy = -1 if xf.get('flipV') == '1' else 1
    a, b, c, d = math.cos(angle)*fx, math.sin(angle)*fx, -math.sin(angle)*fy, math.cos(angle)*fy
    own = (a, b, c, d, x+w/2-a*w/2-c*h/2, y+h/2-b*w/2-d*h/2)
    matrix = native.compose(record['parentMatrix'], own)
    ox, oy = native.point(matrix, *offset)
    ew, eh = extent if extent is not None else (w, h)
    return {'box': {'x': ox/native.EMU, 'y': oy/native.EMU, 'w': ew/native.EMU, 'h': eh/native.EMU},
            'transform': list(matrix[:4]), 'rotation': 0}


def target_body(records, element):
    """Resolve a stable text target to its shape body or individual table cell."""
    node = records[element['nativeId']]['node']
    target = element.get('target', {})
    if target.get('kind') == 'tableCell':
        node = node.find('.//a:tbl', NS).findall('a:tr', NS)[target['row']].findall('a:tc', NS)[target['column']]
    return text_body(node)


def apply_edits(source, mode, overrides, output, chart_scenes=()):
    """Patch editor text targets in isolation, preserving native component structure."""
    parts = native.read_parts(source)
    original_parts = dict(parts)
    source_scenes = scenes(source, mode)
    for scene in source_scenes:
        changed_elements = [e for e in scene['elements'] if str(scene['number']) + '.' + e['id'] in overrides]
        if not changed_elements:
            continue
        if any(e.get('target', {}).get('layer', 'slide') != 'slide' for e in changed_elements):
            privatize_ancestors(parts, scene['part'])
        layers = layer_roots(parts, scene['part'])
        for element in changed_elements:
            layer = element.get('target', {}).get('layer', 'slide')
            part, root = layers[layer]
            records = native.scene_nodes(root, native.ancestors_for(parts, part))
            edit_body(target_body(records, element), overrides[str(scene['number']) + '.' + element['id']])
        changed_layers = {e.get('target', {}).get('layer', 'slide') for e in changed_elements}
        for layer in changed_layers:
            part, root = layers[layer]
            parts[part] = native.xml_bytes(root)
    for chart_scene in chart_scenes:
        scene = next((s for s in source_scenes if s['number'] == chart_scene['number']), None)
        if scene is not None:
            editor_chart.materialize(parts, scene, chart_scene['elements'], overrides)
    temporary = Path(str(output) + '.writing')
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, payload in parts.items():
                archive.writestr(name, payload)
        temporary.replace(output)
        report_path = Path(output).with_suffix('.layout.json')
        if report_path.exists():
            report = json.loads(report_path.read_text())
            report['outputSha256'] = hashlib.sha256(Path(output).read_bytes()).hexdigest()
            report['editorTextOverrides'] = overrides
            edited_parts = {name for name, payload in parts.items() if original_parts.get(name) != payload}
            report['editorChangedParts'] = sorted(edited_parts)
            if report.get('mode') == 'fidelity':
                prior = set(report.get('changedParts', []))
                report['changedParts'] = sorted(prior | edited_parts)
                report['unchangedSourceParts'] = max(0, report.get('unchangedSourceParts', 0) - len((edited_parts - prior) & original_parts.keys()))
                report['baselineVisualPartsByteIdentical'] = not edited_parts and report.get('baselineVisualPartsByteIdentical', False)
            native.write_json_atomic(report_path, report)
    finally:
        temporary.unlink(missing_ok=True)


def layer_roots(parts, part):
    """Return a slide's editable XML layers with stable logical names."""
    result = {'slide': (part, native.parse_xml(parts[part]))}
    for name, root in native.ancestors_for(parts, part):
        result['master' if '/slideMasters/' in name else 'layout'] = (name, root)
    return result


def privatize_ancestors(parts, slide_part):
    """Clone a slide's layout/master chain before changing shared inherited text."""
    owner = slide_part
    clones = {}
    for index, (original, _) in enumerate(native.ancestors_for(parts, slide_part)):
        stem = Path(slide_part).stem
        destination = posixpath.join(posixpath.dirname(original), f'editor-{stem}-{index}.xml')
        clones[original] = destination
        parts[destination] = parts[original]
        if native.rel_path(original) in parts:
            parts[native.rel_path(destination)] = parts[native.rel_path(original)]
        rel_file = native.rel_path(owner)
        relations = native.parse_xml(parts[rel_file])
        for relation in relations:
            if native.resolve_target(owner, relation.get('Target', '')) == original:
                relation.set('Target', posixpath.relpath(destination, posixpath.dirname(owner)))
        parts[rel_file] = native.xml_bytes(relations)
        kind = 'slideMaster' if '/slideMasters/' in original else 'slideLayout'
        native.add_content_type(parts, destination, f'application/vnd.openxmlformats-officedocument.presentationml.{kind}+xml')
        owner = destination
    for original, destination in clones.items():
        rel_file = native.rel_path(destination)
        if rel_file in parts:
            relations = native.parse_xml(parts[rel_file])
            for relation in relations:
                target = native.resolve_target(destination, relation.get('Target', ''))
                if target in clones:
                    relation.set('Target', posixpath.relpath(clones[target], posixpath.dirname(destination)))
            parts[rel_file] = native.xml_bytes(relations)
        if '/slideMasters/' in destination:
            register_master(parts, destination)


def register_master(parts, part):
    """Declare a private master in the presentation relationship and master lists."""
    presentation_part = 'ppt/presentation.xml'
    rel_file = native.rel_path(presentation_part)
    relations = native.parse_xml(parts[rel_file])
    ident = 'rIdEditorMaster' + Path(part).stem
    ET.SubElement(relations, '{http://schemas.openxmlformats.org/package/2006/relationships}Relationship',
        Id=ident, Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster',
        Target=posixpath.relpath(part, 'ppt'))
    parts[rel_file] = native.xml_bytes(relations)
    presentation = native.parse_xml(parts[presentation_part])
    masters = presentation.find('p:sldMasterIdLst', NS)
    if masters is None:
        masters = ET.Element(native.q('p', 'sldMasterIdLst'))
        presentation.insert(0, masters)
    next_id = max([int(master.get('id')) for master in masters] + [2147483647]) + 1
    ET.SubElement(masters, native.q('p', 'sldMasterId'), {'id': str(next_id), native.q('r', 'id'): ident})
    parts[presentation_part] = native.xml_bytes(presentation)


def parent_ids(record, records):
    """Yield parent groups to honor hidden ancestors."""
    parent = record.get('parentId')
    while parent:
        yield parent
        parent = records[parent].get('parentId')


def scenes(source, mode):
    """Build editor scenes with patchable native or responsive semantic IDs."""
    parts = native.read_parts(source)
    presentation = native.parse_xml(parts['ppt/presentation.xml'])
    size = presentation.find('p:sldSz', NS)
    dimensions = {'width': int(size.get('cx')) / native.EMU, 'height': int(size.get('cy')) / native.EMU}
    rels = native.relationships(parts, 'ppt/presentation.xml')
    output = []
    responsive_numbers = [5, 10, 21, 38, 50, 64, 68]
    for index, sid in enumerate(presentation.findall('p:sldIdLst/p:sldId', NS)):
        part = rels[sid.get(native.q('r', 'id'))]['target']
        root = native.parse_xml(parts[part])
        ancestors = native.ancestors_for(parts, part)
        number = responsive_numbers[index] if mode == 'responsive' else index + 1
        elements = []
        chart_instances = []
        for layer, (layer_part, layer_root) in reversed(list(layer_roots(parts, part).items())):
            if layer != 'slide' and root.get('showMasterSp') == '0':
                continue
            ancestors = native.ancestors_for(parts, layer_part)
            theme = theme_context(parts, layer_part, ancestors)
            records = native.scene_nodes(layer_root, ancestors)
            descriptors = native.describe_scene(parts, layer_part, dimensions)
            for item in descriptors:
                if item['kind'] == 'chart' and not item['hidden'] and item.get('box'):
                    owner = item['name'].removeprefix(f'{number}.') if mode == 'responsive' and item['name'].startswith(f'{number}.') else item['id']
                    chart_instances.append({'id': owner if layer == 'slide' else layer + '.' + owner, 'box': item['box']})
                if item['kind'] not in ('shape', 'table') or not item.get('box') or item['hidden']:
                    continue
                if layer != 'slide' and item.get('placeholder'):
                    continue
                record = records[item['id']]
                if any(records[parent]['hidden'] for parent in parent_ids(record, records)):
                    continue
                node = record['node']
                logical_id = item['name'].removeprefix(f'{number}.') if mode == 'responsive' and item['name'].startswith(f'{number}.') else item['id']
                if item['name'].startswith('editor-chart:'):
                    logical_id = item['name'].removeprefix('editor-chart:')
                elif layer != 'slide':
                    logical_id = layer + '.' + logical_id
                ph = item.get('placeholder') or {}
                role = 'title' if ph.get('type') in ('title', 'ctrTitle') or 'title' in item['name'].lower() else 'paragraph'
                targets = []
                if item['kind'] == 'shape' and text_body(node) is not None and body_text(text_body(node)).strip():
                    targets.append((logical_id, node, item['name'], {'kind': 'shape', 'ownerId': logical_id, 'nativeId': item['id']}, text_geometry(record)))
                elif item['kind'] == 'table':
                    table = node.find('.//a:tbl', NS)
                    widths = [int(col.get('w')) for col in table.findall('a:tblGrid/a:gridCol', NS)]
                    rows = table.findall('a:tr', NS)
                    heights = [int(row.get('h')) for row in rows]
                    _, _, frame_w, frame_h = native.transform_values(record['effectiveTransform'])
                    sx, sy = frame_w / (sum(widths) or 1), frame_h / (sum(heights) or 1)
                    for ri, row in enumerate(rows):
                        for ci, cell in enumerate(row.findall('a:tc', NS)):
                            if cell.get('hMerge') == '1' or cell.get('vMerge') == '1' or text_body(cell) is None:
                                continue
                            ident = f'{logical_id}/cell/{ri}/{ci}'
                            geometry = text_geometry(record, (sum(widths[:ci])*sx, sum(heights[:ri])*sy),
                                (sum(widths[ci:ci+int(cell.get('gridSpan', 1))])*sx, sum(heights[ri:ri+int(cell.get('rowSpan', 1))])*sy))
                            targets.append((ident, cell_proxy(cell), f'{item["name"]}, row {ri+1}, column {ci+1}',
                                {'kind': 'tableCell', 'ownerId': logical_id, 'nativeId': item['id'], 'row': ri, 'column': ci}, geometry))
                for ident, text_node, name, target, geometry in targets:
                    value = body_text(text_body(text_node))
                    elements.append({'id': ident, 'nativeId': item['id'], 'name': name,
                        'text': value, 'originalText': value, **geometry, 'role': role if target['kind'] == 'shape' else 'paragraph',
                        'editable': True, 'target': {**target, 'layer': layer}, 'style': style_for(text_node, ancestors, item.get('typography'), theme),
                        'paragraphs': rich_paragraphs(text_node, ancestors, theme)})
        if elements and not any(e['role'] == 'title' for e in elements):
            candidates = [e for e in elements if len(e['text']) < 300]
            if candidates:
                max(candidates, key=lambda e: e['style']['fontSize'])['role'] = 'title'
        title = next((e['text'] for e in elements if e['role'] == 'title'), f'Slide {number}')
        output.append({'schemaVersion': 5, 'number': number, 'title': title, 'hidden': root.get('show') == '0',
                       **dimensions, 'elements': elements, 'charts': chart_instances, 'part': part})
    return output


def normalize_generated_ids(source, output):
    """Repair PptxGenJS table ID collisions without changing semantic names.

    PptxGenJS 4 computes table IDs separately from shapes. Only duplicate table
    IDs are reassigned; an unexpected collision fails rather than guessing how
    to remap connector/animation references. Used on generated decks only.
    """
    parts = native.read_parts(source)
    for name, payload in list(parts.items()):
        if not re.fullmatch(r'ppt/slides/slide\d+\.xml', name):
            continue
        root = native.parse_xml(payload)
        parents = {child: parent for parent in root.iter() for child in parent}
        props = list(root.iter(native.q('p', 'cNvPr')))
        next_id = max(int(p.get('id')) for p in props) + 1
        seen, changed = set(), False
        for prop in props:
            ident = prop.get('id')
            if ident in seen:
                owner = parents.get(parents.get(prop))
                if owner is None or owner.find('.//a:tbl', NS) is None:
                    raise ValueError('Unexpected duplicate generated ID: ' + ident)
                prop.set('id', str(next_id))
                next_id += 1
                changed = True
            seen.add(prop.get('id'))
        if changed:
            parts[name] = native.xml_bytes(root)
    temporary = Path(str(output) + '.writing')
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, payload in parts.items():
                archive.writestr(name, payload)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def background(source, mode, number, output, chart_elements=()):
    """Render one slide without editable text using isolated Office processes."""
    scene = next(s for s in scenes(source, mode) if s['number'] == number)
    parts = native.read_parts(source)
    layers = layer_roots(parts, scene['part'])
    layers['slide'][1].attrib.pop('show', None)
    indexes = {layer: native.scene_nodes(root, native.ancestors_for(parts, part)) for layer, (part, root) in layers.items()}
    for element in scene['elements']:
        if element['editable']:
            layer = element.get('target', {}).get('layer', 'slide')
            body = target_body(indexes[layer], element)
            for paragraph in body.findall('a:p', NS):
                body.remove(paragraph)
            paragraph = ET.SubElement(body, native.q('a', 'p'))
            properties = ET.SubElement(paragraph, native.q('a', 'pPr'))
            ET.SubElement(properties, native.q('a', 'buNone'))
    measured_owners = {element['target']['ownerId'] for element in chart_elements if element.get('target', {}).get('kind') == 'chartText'}
    for frame in editor_chart.chart_frames(parts, scene):
        if frame['ownerId'] not in measured_owners:
            continue
        part, root = layers[frame['layer']]
        record = native.scene_nodes(root, native.ancestors_for(parts, part))[frame['id']]
        editor_chart.hide_chart(parts, part, record['node'], f'background-{number}-{frame["layer"]}-{frame["id"]}')
    for part, root in layers.values():
        parts[part] = native.xml_bytes(root)
    presentation = native.parse_xml(parts['ppt/presentation.xml'])
    rels = native.relationships(parts, 'ppt/presentation.xml')
    ids = presentation.find('p:sldIdLst', NS)
    for sid in list(ids):
        if rels[sid.get(native.q('r', 'id'))]['target'] != scene['part']:
            ids.remove(sid)
    parts['ppt/presentation.xml'] = native.xml_bytes(presentation)
    soffice = os.environ.get('SOFFICE_BIN') or shutil.which('soffice')
    pdftoppm = os.environ.get('PDFTOPPM_BIN') or shutil.which('pdftoppm')
    if not soffice or not pdftoppm:
        raise RuntimeError('Install LibreOffice and Poppler for slide backgrounds')
    with tempfile.TemporaryDirectory(prefix='pptx-editor-preview-') as directory:
        folder = Path(directory)
        deck = folder / 'background.pptx'
        with zipfile.ZipFile(deck, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, payload in parts.items():
                archive.writestr(name, payload)
        subprocess.run([soffice, '-env:UserInstallation=' + (folder / 'profile').as_uri(),
                        '--headless', '--convert-to', 'pdf', '--outdir', str(folder), str(deck)],
                       check=True, capture_output=True, timeout=70)
        target = folder / 'image'
        subprocess.run([pdftoppm, '-f', '1', '-singlefile', '-scale-to', '1600', '-png',
                        str(folder / 'background.pdf'), str(target)], check=True, capture_output=True, timeout=30)
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(target.with_suffix('.png'), output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--mode', choices=['fidelity', 'responsive'], default='fidelity')
    parser.add_argument('--output', required=True)
    parser.add_argument('--background', type=int)
    parser.add_argument('--normalize-ids', action='store_true')
    parser.add_argument('--apply-edits')
    parser.add_argument('--chart-scenes')
    parser.add_argument('--chart-text', type=int)
    args = parser.parse_args()
    if args.chart_text is not None:
        scene = next(s for s in scenes(args.source, args.mode) if s['number'] == args.chart_text)
        native.write_json_atomic(Path(args.output), {'number': scene['number'], 'elements': editor_chart.extract(args.source, scene)})
    elif args.apply_edits:
        chart_scenes = json.loads(Path(args.chart_scenes).read_text()) if args.chart_scenes else []
        apply_edits(args.source, args.mode, json.loads(Path(args.apply_edits).read_text()), args.output, chart_scenes)
    elif args.normalize_ids:
        normalize_generated_ids(args.source, args.output)
    elif args.background is not None:
        chart_data = json.loads(Path(args.chart_scenes).read_text()) if args.chart_scenes else {}
        chart_elements = chart_data.get('elements', []) if isinstance(chart_data, dict) else next((s['elements'] for s in chart_data if s['number'] == args.background), [])
        background(args.source, args.mode, args.background, args.output, chart_elements)
    else:
        native.write_json_atomic(Path(args.output), scenes(args.source, args.mode))
