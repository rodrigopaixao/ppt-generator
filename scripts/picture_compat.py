"""Preserve source SVG artwork while providing portable raster picture blips."""
import posixpath
import xml.etree.ElementTree as ET
from pathlib import Path
from native_deck import NS, q, parse_xml, xml_bytes, relationships, rel_path, add_content_type


def repair_svg_pictures(parts, fallbacks):
    """Link PNG fallbacks only for SVG pictures without a normal image relation.

    parts is the mutable OPC package. fallbacks maps source SVG part names to
    private PNG paths prepared by Sharp. SVG relationships and picture geometry
    remain unchanged. Returns an audit list; missing generated media is an error.
    """
    repaired = []
    svg_tag = '{http://schemas.microsoft.com/office/drawing/2016/SVG/main}svgBlip'
    package_ns = 'http://schemas.openxmlformats.org/package/2006/relationships'
    for owner in list(parts):
        if not owner.endswith('.xml') or not owner.startswith(('ppt/slides/', 'ppt/slideLayouts/', 'ppt/slideMasters/')):
            continue
        root = parse_xml(parts[owner]); changed = False
        rels = relationships(parts, owner)
        relation_path = rel_path(owner)
        rel_root = parse_xml(parts[relation_path]) if relation_path in parts else ET.Element('{'+package_ns+'}Relationships')
        for picture in root.findall('.//p:pic', NS):
            blip = picture.find('p:blipFill/a:blip', NS)
            if blip is None or blip.get(q('r', 'embed')):
                continue
            svg = blip.find('.//'+svg_tag)
            if svg is None:
                continue
            original = rels.get(svg.get(q('r', 'embed')))
            if not original:
                continue
            # relationships() returns a descriptor, not just a target string.
            source = original['target']
            if source not in fallbacks:
                raise ValueError(f'No prepared SVG fallback for {source}')
            target = source+'.fallback.png'
            parts[target] = Path(fallbacks[source]).read_bytes()
            add_content_type(parts, target, 'image/png')
            used = {node.get('Id') for node in rel_root}
            index = 1
            while 'rIdSvgFallback'+str(index) in used:
                index += 1
            rid = 'rIdSvgFallback'+str(index)
            ET.SubElement(rel_root, '{'+package_ns+'}Relationship', Id=rid,
                Type=NS['r']+'/image', Target=posixpath.relpath(target, posixpath.dirname(owner)))
            blip.set(q('r', 'embed'), rid)
            repaired.append({'owner':owner, 'svg':source, 'fallback':target})
            changed = True
        if changed:
            parts[owner] = xml_bytes(root)
            parts[relation_path] = xml_bytes(rel_root)
    return repaired
