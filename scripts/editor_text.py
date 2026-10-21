"""Edit DrawingML text while retaining paragraph and run formatting."""
import copy
from difflib import SequenceMatcher
import xml.etree.ElementTree as ET

from native_deck import NS, q, local


def text_body(node):
    """Find a shape, table-cell or chart text body without flattening descendants."""
    if local(node.tag) in ('txBody', 'rich'):
        return node
    for selector in ('p:txBody', 'a:txBody', 'c:tx/c:rich'):
        body = node.find(selector, NS)
        if body is not None:
            return body
    return None


def paragraph_text(paragraph):
    """Read visible runs, fields and soft breaks in document order."""
    return ''.join('\n' if local(child.tag) == 'br' else
                   ''.join(t.text or '' for t in child.iter(q('a', 't')))
                   for child in paragraph if local(child.tag) in ('r', 'fld', 'br'))


def body_text(body):
    """Return plain editable text while preserving hard and soft line breaks."""
    return '\n'.join(paragraph_text(p) for p in body.findall('a:p', NS))


def edit_body(body, value):
    """Apply a plain-text edit using unchanged characters as formatting anchors.

    Retain paragraph properties, bullets, hyperlinks, run effects and field
    metadata. Inserted characters inherit the adjacent run. Edited fields become
    literal runs; untouched fields remain fields. Never modify sibling objects.
    """
    original = body_text(body)
    if original == value:
        return
    paragraphs = body.findall('a:p', NS)
    tokens = []
    for pi, paragraph in enumerate(paragraphs):
        for child in paragraph:
            kind = local(child.tag)
            if kind not in ('r', 'fld', 'br'):
                continue
            text = '\n' if kind == 'br' else ''.join(t.text or '' for t in child.iter(q('a', 't')))
            tokens.extend((pi, child) for _ in text)
        if pi < len(paragraphs) - 1:
            tokens.append((pi, None))
    fallback = (0, None)
    styles = []
    for action, start, end, new_start, new_end in SequenceMatcher(None, original, value).get_opcodes():
        if action == 'equal':
            styles.extend(tokens[start:end])
        elif action in ('insert', 'replace'):
            basis = tokens[start] if start < len(tokens) else tokens[-1] if tokens else fallback
            if basis[1] is None and start:
                basis = tokens[start - 1]
            styles.extend([basis] * (new_end - new_start))
    for paragraph in paragraphs:
        body.remove(paragraph)
    offset = 0
    for line in value.split('\n'):
        basis_index = styles[offset][0] if offset < len(styles) else len(paragraphs) - 1
        basis = paragraphs[max(0, basis_index)] if paragraphs else ET.Element(q('a', 'p'))
        paragraph = ET.Element(q('a', 'p'), dict(basis.attrib))
        props = basis.find('a:pPr', NS)
        if props is not None:
            paragraph.append(copy.deepcopy(props))
        index = 0
        while index < len(line):
            source = styles[offset + index][1]
            finish = index + 1
            while finish < len(line) and styles[offset + finish][1] is source:
                finish += 1
            content = line[index:finish]
            field = source is not None and local(source.tag) == 'fld' and content == ''.join(t.text or '' for t in source.iter(q('a', 't')))
            run = ET.Element(q('a', 'fld') if field else q('a', 'r'), dict(source.attrib) if field else {})
            prop = source.find('a:rPr', NS) if source is not None else basis.find('a:r/a:rPr', NS)
            if prop is not None:
                run.append(copy.deepcopy(prop))
            ET.SubElement(run, q('a', 't')).text = content
            paragraph.append(run)
            index = finish
        end = basis.find('a:endParaRPr', NS)
        if end is not None:
            paragraph.append(copy.deepcopy(end))
        body.append(paragraph)
        offset += len(line) + 1
