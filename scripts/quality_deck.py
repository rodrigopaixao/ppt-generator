"""Normalização explícita da apresentação editável, com diagnóstico de tipografia.

Este módulo só é chamado pelo perfil quality; o modo fidelity continua intacto.
O texto original não é resumido. Reduz a fonte por medição explícita até o piso
configurável, sem depender do autofit do leitor, recorte ou rasterização. Os mínimos são os escolhidos pelo usuário: corpo 12, matriz/gráfico
10 e notas 8 pt. A fonte Arial é portátil e substituível por quality.font.
"""
import json
import math
import re
import copy
import posixpath
from pathlib import Path
import xml.etree.ElementTree as ET
from native_deck import (NS, EMU, ROOT, q, parse_xml, xml_bytes, scene_nodes,
                         ancestors_for, box_for, text_of, ensure, materialize_transform, apply_box,
                         rel_path, relationships, replace_text, placeholder_of)

METRICS = json.loads((ROOT/'data/font-metrics.json').read_text())


def measure_lines(text, width, size, bold=False, tracking=0):
    """Estima quebra por avanços Arial em em, com margem horizontal de 3%.

    text conserva quebras explícitas; width é largura útil em polegadas; size
    é pt; tracking é o espaçamento adicional entre letras em pt. Usa métricas do projeto, sem depender de fontes instaladas no servidor.
    Não certifica todos os renderizadores; a revisão visual complementa a medida.
    """
    face = METRICS['widths']['bold' if bold else 'regular']
    total = 0
    for paragraph in text.split('\n'):
        used, lines = 0, 1
        for word in re.findall(r'\S+\s*', paragraph):
            length = sum(face.get(char, face.get('?', 0.55)) for char in word)*size/72*1.03 + max(0,len(word)-1)*tracking/72
            if used and used+length > max(width, 0.01):
                lines += 1
                used = 0
            if length > max(width, 0.01):
                lines += max(0, math.ceil(length/max(width, 0.01))-1)
                used = length % max(width, 0.01)
            else:
                used += length
        total += lines
    return total


def measure_rich_lines(paragraph, width, fallback_size):
    """Mede a quebra de palavras ponderando cada run regular/negrito em pt.

    Evita tratar o parágrafo inteiro como negrito quando só seu título o é. A
    mesma medição dimensiona a lista e ancora seus indicadores ao primeiro verso.
    """
    widths, chars = [], []
    default = paragraph.find('a:pPr/a:defRPr',NS)
    for run in paragraph:
        if run.tag not in (q('a','r'),q('a','fld')):
            continue
        prop = run.find('a:rPr',NS)
        prop = prop if prop is not None else default
        size = float(prop.get('sz',fallback_size*100))/100 if prop is not None else fallback_size
        bold = prop.get('b','1' if default is not None and default.get('b')=='1' else '0')=='1' if prop is not None else False
        tracking = float(prop.get('spc',0))/100 if prop is not None else 0
        face = METRICS['widths']['bold' if bold else 'regular']
        for char in ''.join(t.text or '' for t in run.iter(q('a','t'))):
            chars.append(char)
            widths.append(face.get(char,0.55)*size/72*1.03+tracking/72)
    used,lines = 0,1
    for word in re.finditer(r'\S+\s*',''.join(chars)):
        length = sum(widths[word.start():word.end()])
        if used and used+length>width:
            lines += 1
            used = 0
        if length>width:
            lines += max(0,math.ceil(length/max(0.01,width))-1)
            used = length%max(0.01,width)
        else:
            used += length
    return lines


def role_for(node, box, text, table=False, custom=False):
    """Classifica título, corpo, matriz/rótulo e nota por semântica e geometria.

    O papel explícito quality.roles['slide.eID'] prevalece no chamador. Tabelas
    e rótulos pequenos são dense; notas de fonte e rodapés são note. Títulos são
    placeholders ou caixas longas no cabeçalho. custom preserva papéis já criados
    pelo construtor JS, cujas fontes foram medidas antes da serialização.
    """
    if table:
        return 'dense'
    if re.match(r'^\s*(Source:|Sources:|Note:|Notes:)', text, re.I) or box['y'] >= 6.85:
        return 'note'
    ph = node.find('p:nvSpPr/p:nvPr/p:ph', NS)
    if (ph is not None and ph.get('type') in ('title', 'ctrTitle')) or (box['y'] < 1.3 and box['h'] < 1.1 and box['w'] > 8 and len(text) > 35):
        return 'title'
    if box['y'] < 0.65 or box['h'] < 0.34 or (box['w'] < 2.5 and box['h'] < 1):
        return 'dense'
    return 'body'


def heading_level(config, key, role, text, reference_size, box):
    """Resolve o nível semântico antes de escolher um tamanho padrão.

    config.hierarchy.roles associa IDs a níveis explícitos. Sem override, títulos
    de slide usam title; tamanho original e caixa distinguem os níveis restantes.
    O tamanho original serve à classificação, nunca cria um novo token por slide.
    """
    explicit = config.get('hierarchy',{}).get('roles',{}).get(key)
    if explicit:
        return explicit
    if role == 'title' or reference_size >= 20:
        return 'title'
    if reference_size >= 18:
        return 'display'
    if reference_size >= 16:
        return 'statement'
    if reference_size >= 14:
        return 'subtitle'
    if box['y'] < 0.65:
        return 'kicker'
    if text.strip().isupper():
        return 'section'
    return 'component' if reference_size >= 11 else 'chartTitle'


def normalize_template_typography(parts, config):
    """Aplica o token title também a masters/layouts para futuros placeholders.

    parts é o pacote OPC editável. Apenas estilos de título e placeholders title/
    ctrTitle são alterados; placeholders body de capas usam seus tokens próprios
    conforme o tamanho original. Tabelas e gráficos mantêm seu pipeline.
    """
    hierarchy = config.get('hierarchy',{})
    if not hierarchy.get('enabled',False):
        return
    size = hierarchy['sizes']['title']
    for part in list(parts):
        if not part.endswith('.xml') or not any(folder in part for folder in ('/slideMasters/','/slideLayouts/')):
            continue
        root = parse_xml(parts[part])
        targets = [(target,size) for target in root.findall('p:txStyles/p:titleStyle',NS)]
        for node in root.iter(q('p','sp')):
            ph = node.find('p:nvSpPr/p:nvPr/p:ph',NS)
            if ph is not None and ph.get('type') in ('title','ctrTitle'):
                body = node.find('p:txBody',NS)
                if body is not None:
                    targets.append((body,size))
            elif ph is not None:
                body = node.find('p:txBody',NS)
                original = max([float(prop.get('sz'))/100 for prop in node.iter() if prop.tag in (q('a','rPr'),q('a','defRPr')) and prop.get('sz')] or [0])
                level = 'sectionCoverTitle' if original>62 else 'coverTitle' if original>=48 else 'coverNumber' if original>=24 and text_of(node).strip().isdigit() else None
                if body is not None and level:
                    targets.append((body,hierarchy['sizes'][level]))
        for target,target_size in targets:
            for prop in target.iter():
                if prop.tag in (q('a','defRPr'),q('a','rPr'),q('a','endParaRPr')):
                    prop.set('sz',str(round(target_size*100)))
        if targets:
            parts[part] = xml_bytes(root)


def normalize_body(body, font, size, role, height, width, padding, custom=False, preserve_layout=False, paragraph_sizes=None, paragraph_gap=0, rich_measure=False):
    """Materializa fontes, remove margens impossíveis e impede autofit oculto.

    body é p:txBody ou a:txBody. height/width são polegadas locais. padding é
    polegadas e é limitado pela altura real. custom conserva tamanhos explícitos; preserve_layout mantém a faixa funcional
    de ícones mesmo quando a tipografia é fixa. paragraph_sizes fixa fontes em pt
    por parágrafo; paragraph_gap é o espaço entre parágrafos em polegadas, também
    somado à altura medida. rich_measure pondera os runs de ênfase na quebra.
    Espaçamentos são materializados para
    impedir que margens de parágrafo do master alterem a altura das linhas.
    Retorna {requiredHeight, availableHeight, fontSizes}, para auditoria.
    """
    bp = ensure(body, q('a', 'bodyPr'))
    vertical = bp.get('vert') in ('vert', 'vert270', 'eaVert')
    if vertical:
        height, width = width, height
    count = len(body.findall('a:p', NS))
    inset = min(padding, max(0, (height-size/72*1.07)/2))
    for attr in ('tIns', 'bIns'):
        bp.set(attr, str(round(inset*EMU)))
    for attr in ('lIns', 'rIns'):
        # Large left gutters reserve an icon lane. They are functional layout,
        # whereas the impossible top/bottom margins were the inversion defect.
        original = int(bp.get(attr, 0))/EMU
        chosen = original if (not custom or preserve_layout) and attr == 'lIns' and original >= 0.14 and width > 1 else min(padding,max(0,(width-size/72)/2))
        bp.set(attr, str(round(chosen*EMU)))
    for child in list(bp):
        if child.tag in (q('a', 'normAutofit'), q('a', 'spAutoFit')):
            bp.remove(child)
    if bp.find('a:noAutofit', NS) is None:
        position = next((i for i, n in enumerate(bp) if n.tag in (q('a','scene3d'),q('a','sp3d'),q('a','flatTx'),q('a','extLst'))), len(bp))
        bp.insert(position, ET.Element(q('a','noAutofit')))
    heights, sizes = [], set()
    paragraphs = body.findall('a:p',NS)
    for pi,paragraph in enumerate(paragraphs):
        if not ''.join(n.text or '' for n in paragraph.iter(q('a', 't'))).strip():
            body.remove(paragraph)
            continue
        pp = paragraph.find('a:pPr', NS)
        if pp is None:
            pp = ET.Element(q('a', 'pPr'))
            paragraph.insert(0, pp)
        for tag in ('lnSpc', 'spcBef', 'spcAft'):
            for old in pp.findall('a:'+tag, NS):
                pp.remove(old)
        line = ET.Element(q('a', 'lnSpc'))
        ET.SubElement(line, q('a', 'spcPct'), val='100000' if role == 'dense' else '110000')
        pp.insert(0, line)
        for position, tag in enumerate(('spcBef', 'spcAft'), 1):
            space = ET.Element(q('a', tag))
            ET.SubElement(space, q('a', 'spcPts'), val=str(round(paragraph_gap*72*100)) if tag=='spcAft' and pi<len(paragraphs)-1 else '0')
            pp.insert(position, space)
        props = [ensure(pp, q('a', 'defRPr'))]
        for run in paragraph:
            if run.tag in (q('a', 'r'), q('a', 'fld')):
                prop = run.find('a:rPr', NS)
                if prop is None:
                    prop = ET.Element(q('a', 'rPr'))
                    run.insert(0, prop)
                props.append(prop)
            elif run.tag == q('a', 'endParaRPr'):
                props.append(run)
        for prop in props:
            actual = paragraph_sizes[min(pi,len(paragraph_sizes)-1)] if paragraph_sizes else float(prop.get('sz', size*100))/100 if custom else size
            prop.set('sz', str(round(actual*100)))
            sizes.add(actual)
            for face in ('latin', 'ea', 'cs'):
                ensure(prop, q('a', face)).set('typeface', font)
            # Missing symbol fonts must not replace ordinary Unicode characters.
            symbol = prop.find('a:sym', NS)
            if symbol is not None:
                prop.remove(symbol)
        text = ''.join(n.text or '' for n in paragraph.iter(q('a', 't'))).strip()
        paragraph_size = max(float(p.get('sz', size*100))/100 for p in props)
        bold = any(p.get('b') == '1' for p in props)
        left = max(0, int(pp.get('marL', 0)))/EMU
        horizontal = (int(bp.get('lIns',0))+int(bp.get('rIns',0)))/EMU
        run_props = paragraph.findall('a:r/a:rPr',NS)+paragraph.findall('a:fld/a:rPr',NS)
        default_tracking = float(ensure(pp,q('a','defRPr')).get('spc',0))/100
        tracking = max([float(p.get('spc',default_tracking*100))/100 for p in run_props] or [default_tracking])
        lines = measure_rich_lines(paragraph,max(0.01,width-horizontal-left),paragraph_size) if rich_measure else measure_lines(text, max(0.01, width-horizontal-left), paragraph_size, bold, tracking)
        heights.append(lines*paragraph_size/72*1.1+(paragraph_gap if pi<len(paragraphs)-1 else 0))
    if body.find('a:p', NS) is None:
        # CT_TextBody requires at least one paragraph. An absent paragraph makes
        # readers invent one using the master's large default font, inflating
        # blank agenda cells. 1pt applies to this invisible structural marker.
        paragraph = ET.SubElement(body,q('a','p'))
        pp = ET.SubElement(paragraph,q('a','pPr'))
        prop = ET.SubElement(pp,q('a','defRPr'),sz='100')
        ET.SubElement(prop,q('a','latin'),typeface=font)
        ET.SubElement(paragraph,q('a','endParaRPr'),sz='100')
    return {'requiredHeight': sum(heights)+2*inset, 'availableHeight': height,
            'fontSizes': sorted(sizes), 'paragraphs': count, 'paragraphHeights':heights}


def fit_body_size(body, font, preferred, minimum, role, height, width, padding, settings):
    """Escolhe a maior fonte até o padrão que caiba na caixa atual.

    preferred é o tamanho nominal, minimum é o piso configurável, settings define
    enabled e step (pt). A medição usa cópias para não destruir runs durante as
    tentativas. Sem espaço no piso, retorna o piso; reflow/paginação vêm depois.
    Nunca amplia texto acima do nominal nem modifica conteúdo.
    """
    size = preferred
    if not settings.get('enabled', True):
        return size
    step = float(settings.get('step', 0.25))
    if not math.isfinite(step) or step < 0.01:
        raise ValueError('fontFit.step precisa ser finito e pelo menos 0.01 pt')
    while size > minimum:
        measured = normalize_body(copy.deepcopy(body), font, size, role, height, width, padding)
        if measured['requiredHeight'] <= measured['availableHeight']+0.01:
            return size
        size = max(minimum, round(size-step, 2))
    return size


def fit_table_size(table, font, preferred, minimum, height, padding, custom, settings):
    """Reduz a tabela como um conjunto, preservando fonte uniforme entre células.

    Larguras/mesclas vêm do DrawingML real. Calcula a altura mínima de todas as
    linhas; distribui a necessidade das células com rowSpan nas linhas cobertas.
    Só reduz se a tabela inteira não couber no nominal. No piso, o chamador pode
    reorganizar as linhas ou sinalizar falta de espaço sem cortar conteúdo.
    """
    size = preferred
    if not settings.get('enabled', True):
        return size
    step = float(settings.get('step', 0.25))
    if not math.isfinite(step) or step < 0.01:
        raise ValueError('fontFit.step precisa ser finito e pelo menos 0.01 pt')
    widths = [int(col.get('w'))/EMU for col in table.findall('a:tblGrid/a:gridCol', NS)]
    rows = table.findall('a:tr', NS)
    while size > minimum:
        heights, spanning = [0.18]*len(rows), []
        for ri, row in enumerate(rows):
            for ci, cell in enumerate(row.findall('a:tc', NS)):
                if cell.get('hMerge') == '1' or cell.get('vMerge') == '1':
                    continue
                body = cell.find('a:txBody', NS)
                if body is None:
                    continue
                props = cell.find('a:tcPr', NS)
                gutter = int(props.get('marL',0))/EMU if props is not None else 0
                gutter = gutter if not custom and gutter >= 0.15 and widths[ci] > 0.8 else padding
                width = sum(widths[ci:ci+int(cell.get('gridSpan',1))])-gutter-padding
                measured = normalize_body(copy.deepcopy(body),font,size,'dense',height,width,0)
                required = measured['requiredHeight']+2*padding
                span = int(cell.get('rowSpan',1))
                if span == 1:
                    heights[ri] = max(heights[ri],required)
                else:
                    spanning.append((ri,span,required))
        for start, span, required in spanning:
            end = min(len(rows),start+span)
            deficit = max(0,required-sum(heights[start:end]))/(end-start)
            for ri in range(start,end):
                heights[ri] += deficit
        if sum(heights) <= height+0.01:
            return size
        size = max(minimum,round(size-step,2))
    return size


def complete_categories(parts, minimum, font):
    """Completa caches de categorias ausentes sem alterar nenhum valor numérico.

    Gráficos think-cell podem depender de categorias implícitas aceitas por alguns
    leitores. strLit com o mesmo número de pontos garante categorias Office
    explícitas. Eixos ocultos continuam ocultos. Séries scatter já têm x/y próprios.
    Também materializa fonte mínima em rótulos, eixos e legenda nativos.
    """
    fixed = []
    for name in list(parts):
        if not re.fullmatch(r'ppt/charts/(?:generated-)*chart\d+\.xml', name):
            continue
        root = parse_xml(parts[name])
        default = root.find('c:txPr', NS)
        if default is None:
            default = ET.Element(q('c','txPr'))
            position = next((i for i, n in enumerate(root) if n.tag in (q('c','externalData'),q('c','printSettings'),q('c','userShapes'),q('c','extLst'))), len(root))
            root.insert(position, default)
            ET.SubElement(default, q('a','bodyPr'))
            ET.SubElement(default, q('a','lstStyle'))
            paragraph = ET.SubElement(default, q('a','p'))
            pp = ET.SubElement(paragraph, q('a','pPr'))
            prop = ET.SubElement(pp, q('a','defRPr'), sz=str(round(minimum*100)))
            ET.SubElement(prop, q('a','latin'), typeface=font)
        missing = 0
        for series in root.findall('.//c:barChart/c:ser', NS):
            name_text = ''.join(t.text or '' for t in series.findall('c:tx//c:v', NS))
            # A 2–6% slice cannot contain a 10pt label in these bars. The generated
            # slide prints these exact values in its editable annotation below.
            if 'generated-' in name and name_text in ('Auto', 'Unsecured'):
                labels = series.find('c:dLbls', NS)
                if labels is None:
                    labels = ET.Element(q('c','dLbls'))
                    pos = next((i for i,n in enumerate(series) if n.tag == q('c','cat')), len(series))
                    series.insert(pos, labels)
                values_for_labels = series.findall('c:val//c:pt', NS)
                for index, value in enumerate(values_for_labels):
                    if name_text == 'Auto' or float(value.findtext('c:v', namespaces=NS)) < 8:
                        label = ET.Element(q('c','dLbl'))
                        ET.SubElement(label,q('c','idx'),val=str(index))
                        ET.SubElement(label,q('c','delete'),val='1')
                        for flag in ('showLegendKey','showVal','showCatName','showSerName','showPercent','showBubbleSize'):
                            ET.SubElement(label,q('c',flag),val='0')
                        labels.insert(0,label)
            if series.find('c:cat', NS) is not None:
                continue
            values = series.findall('c:val//c:pt', NS)
            cat = ET.Element(q('c', 'cat'))
            literal = ET.SubElement(cat, q('c', 'strLit'))
            ET.SubElement(literal, q('c', 'ptCount'), val=str(len(values)))
            for index in range(len(values)):
                pt = ET.SubElement(literal, q('c', 'pt'), idx=str(index))
                ET.SubElement(pt, q('c', 'v')).text = str(index+1)
            position = next((i for i, n in enumerate(series) if n.tag == q('c', 'val')), len(series))
            series.insert(position, cat)
            missing += 1
        for prop in root.iter():
            if prop.tag in (q('a', 'rPr'), q('a', 'defRPr'), q('a', 'endParaRPr')):
                prop.set('sz', str(round(minimum*100)))
                ensure(prop, q('a', 'latin')).set('typeface', font)
        parts[name] = xml_bytes(root)
        if missing:
            fixed.append({'part': name, 'series': missing})
    return fixed


def paginate_narrative(parts, number, ident, config, dimensions, content_bottom=7.1):
    """Divide prosa que não cabe no mínimo em continuações com estilo preservado.

    number/ident referenciam um corpo narrativo, nunca um dado de gráfico. Cada
    parágrafo é mantido inteiro com runs/ênfases; a cópia herda master e layout.
    As páginas são inseridas após a origem na ordem nativa da apresentação.
    Retorna as partes criadas e as medidas das páginas, sem perder texto.
    """
    source = f'ppt/slides/slide{number}.xml'
    original = parse_xml(parts[source])
    scene = scene_nodes(original, ancestors_for(parts, source))
    record = scene[ident]
    body = record['node'].find('p:txBody', NS)
    paragraphs = [copy.deepcopy(p) for p in body.findall('a:p', NS)]
    box = {'x': 0.56, 'y': 1.55, 'w': dimensions['width']-1.12, 'h': min(5.55,content_bottom-1.55)}
    content_limit = box['h']/config.get('paginationSafety',1.12)-0.08
    batches, batch = [], []
    for paragraph in paragraphs:
        probe = copy.deepcopy(body)
        for p in probe.findall('a:p', NS):
            probe.remove(p)
        for p in batch+[paragraph]:
            probe.append(copy.deepcopy(p))
        measurement = normalize_body(probe, config['font'], config['type']['body']['size'],
          'body', box['h'], box['w'], 0.025)
        if measurement['requiredHeight'] > content_limit and batch:
            carry = []
            last_text = text_of(batch[-1]).strip()
            if last_text.isupper() and len(last_text) < 80:
                carry.append(batch.pop())
            if batch:
                batches.append(batch)
            batch = carry
        batch.append(paragraph)
    if batch:
        batches.append(batch)
    presentation = parse_xml(parts['ppt/presentation.xml'])
    slides = presentation.find('p:sldIdLst', NS)
    prels = parse_xml(parts['ppt/_rels/presentation.xml.rels'])
    mappings = relationships(parts, 'ppt/presentation.xml')
    source_entry = next(entry for entry in slides if mappings[entry.get(q('r','id'))]['target'] == source)
    position = list(slides).index(source_entry)
    content_types = parse_xml(parts['[Content_Types].xml'])
    maximum = max(int(re.search(r'slide(\d+)\.xml$', name).group(1)) for name in parts if re.fullmatch(r'ppt/slides/slide\d+\.xml', name))
    next_id = max(int(entry.get('id')) for entry in slides)+1
    continuation, measures = [], []
    for page, paragraphs_for_page in enumerate(batches):
        root = copy.deepcopy(original)
        current = scene_nodes(root, ancestors_for(parts, source))[ident]
        target_body = current['node'].find('p:txBody', NS)
        for p in target_body.findall('a:p', NS):
            target_body.remove(p)
        for p in paragraphs_for_page:
            target_body.append(copy.deepcopy(p))
        apply_box(current, {'box': box}, {}, dimensions)
        measured = normalize_body(target_body, config['font'], config['type']['body']['size'],
          'body', box['h'], box['w'], 0.025)
        if measured['requiredHeight'] > box['h']:
            raise ValueError(f'Slide {number}: parágrafo individual não cabe em uma continuação')
        for entry in scene_nodes(root, ancestors_for(parts, source)).values():
            if text_of(entry['node']).strip() == str(number) and entry['node'].tag == q('p','sp'):
                replace_text(entry['node'], f'{number}.{page+1}')
            placeholder = placeholder_of(entry['node'])
            if page > 0 and placeholder and placeholder['type'] in ('title','ctrTitle'):
                replace_text(entry['node'], text_of(entry['node']).strip()+f' (continued {page+1}/{len(batches)})')
        if page == 0:
            target = source
        else:
            maximum += 1
            target = f'ppt/slides/slide{maximum}.xml'
            parts[rel_path(target)] = parts[rel_path(source)]
            rid = f'rIdQuality{maximum}'
            ET.SubElement(prels, q('rel','Relationship'), Id=rid,
              Type=NS['r']+'/slide', Target=posixpath.relpath(target,'ppt'))
            entry = ET.Element(q('p','sldId'), {'id':str(next_id), q('r','id'):rid})
            next_id += 1
            slides.insert(position+page,entry)
            ET.SubElement(content_types, q('ct','Override'), PartName='/'+target,
              ContentType='application/vnd.openxmlformats-officedocument.presentationml.slide+xml')
            continuation.append({'sourceNumber': number, 'part': target, 'page': page+1})
        parts[target] = xml_bytes(root)
        measures.append({'slide': number, 'part':target, 'id':ident, 'page':page+1,
          'role':'body', 'box':box, **measured})
    parts['ppt/presentation.xml'] = xml_bytes(presentation)
    parts['ppt/_rels/presentation.xml.rels'] = xml_bytes(prels)
    parts['[Content_Types].xml'] = xml_bytes(content_types)
    return continuation, measures


def normalize_package(parts, config, dimensions, selection):
    """Aplica a escala centralizada e produz diagnóstico verificável por objeto.

    parts é o mapa OPC editável; config contém tokens e overrides de papéis.
    selection identifica os slides entregues. O relatório inclui medições, fontes
    e problemas restantes; não confunde igualdade de pixels com revisão visual.
    Caixas originais só crescem se houver espaço antes do próximo texto na coluna.
    """
    records, issues, layout_plans = [], [], {}
    normalize_template_typography(parts,config)
    font, scale = config['font'], config['type']
    for number in selection:
        part = f'ppt/slides/slide{number}.xml'
        root = parse_xml(parts[part])
        from layout_constraints import prepare_slide_layout
        plan = prepare_slide_layout(root,parts,part,config,dimensions)
        layout_plans[number] = plan
        scene = scene_nodes(root, ancestors_for(parts, part))
        for ident, record in scene.items():
            node, transform = record['node'], record['effectiveTransform']
            if transform is None or node.tag == q('p', 'grpSp'):
                continue
            box = box_for(transform, record['parentMatrix'])
            text = text_of(node)
            if not text.strip():
                continue
            custom = record['name'].startswith('custom.')
            table = node.find('.//a:tbl', NS)
            role = config.get('roles', {}).get(f'{number}.{ident}', config.get('roles', {}).get(f'{number}.{record["name"]}', role_for(node, box, text, table is not None, custom)))
            if ident in plan.get('notes',[]):
                role = 'note'
            if role not in scale:
                raise ValueError(f'Papel tipográfico desconhecido: {role}')
            limits = scale[role]
            declared = [int(n.get('sz'))/100 for n in node.iter() if n.tag == q('a', 'rPr') and n.get('sz')]
            original_size = max(declared or [limits['min']])
            size = min(limits['max'], max(limits['min'], original_size))
            # Every role resolves to a discrete, reproducible size, rather than 11.37pt.
            size = original_size if custom else limits.get('size', limits['min'])
            if custom and not config.get('referenceTypography',{}).get('elements',{}).get(f'{number}.{record["name"]}',{}).get('locked') and (original_size < limits['min'] or original_size > limits['max']):
                raise ValueError(f'{number}.{record["name"]}: {original_size}pt fora do intervalo {limits}')
            reference = config.get('referenceTypography', {}).get('elements', {}).get(f'{number}.{record["name"]}' if custom else f'{number}.{ident}')
            runs = [r for r in node.findall('p:txBody/a:p/a:r', NS) if text_of(r).strip() or r.find('a:t',NS) is not None]
            short_heading = (not custom and table is None and len(text.strip()) <= 110
                and len(text.strip().splitlines()) <= 2 and any(c.isalpha() for c in text)
                and not any(c.isdigit() for c in text) and runs
                and all(r.find('a:rPr',NS) is not None and r.find('a:rPr',NS).get('b') == '1' for r in runs))
            locked = bool((config.get('referenceTypography',{}).get('enabled',True) or config.get('hierarchy',{}).get('enabled',False)) and reference
                and (role == 'title' or short_heading or reference.get('locked')))
            hierarchy = config.get('hierarchy',{})
            key = f'{number}.{record["name"]}' if custom else f'{number}.{ident}'
            explicit_level = hierarchy.get('roles',{}).get(key)
            locked = locked or bool(hierarchy.get('enabled') and explicit_level)
            level = None
            if locked:
                source_size = reference['size'] if reference and reference.get('size') else size
                level = heading_level(config,key,role,text,source_size,box)
                size = hierarchy['sizes'][level] if hierarchy.get('enabled') else source_size
            if table is not None:
                header_layout = config.get('flow',{}).get('tableHeaders',{}).get(f'{number}.{ident}',{})
                widths = [int(col.get('w'))/EMU for col in table.findall('a:tblGrid/a:gridCol', NS)]
                from layout_constraints import table_overlay_cells, anchor_table_overlays, materialize_vertical_table_labels
                overlays = table_overlay_cells(scene,record,widths)
                preferred_size = size
                size = fit_table_size(table,font,size,limits['min'],box['h'],config['spacing']['tablePadding']/72,custom,config.get('fontFit',{}))
                table_records, required_rows = [], []
                rows = table.findall('a:tr', NS)
                for ri, row in enumerate(rows):
                    height = int(row.get('h'))/EMU
                    required = 0
                    for ci, cell in enumerate(row.findall('a:tc', NS)):
                        if cell.get('hMerge') == '1' or cell.get('vMerge') == '1':
                            continue
                        body = cell.find('a:txBody', NS)
                        if body is None:
                            continue
                        # Table padding belongs to tcPr, not a:bodyPr: avoid counting twice.
                        tcpr = ensure(cell, q('a', 'tcPr'))
                        padding = config['spacing']['tablePadding']/72
                        gutter = int(tcpr.get('marL',0))/EMU
                        gutter = gutter if not custom and gutter >= 0.15 and widths[min(ci,len(widths)-1)] > 0.8 else padding
                        for attr in ('marL', 'marR', 'marT', 'marB'):
                            tcpr.set(attr, str(round((gutter if attr == 'marL' else padding)*EMU)))
                        if ri == 0 and header_layout.get('anchor'):
                            tcpr.set('anchor',header_layout['anchor'])
                        if tcpr.get('anchor') == 'mid':
                            tcpr.set('anchor','ctr')
                        span = int(cell.get('gridSpan', 1))
                        cell_width = sum(widths[ci:ci+span])
                        cell_size = size
                        if ri == 0 and hierarchy.get('enabled'):
                            cell_size = hierarchy['sizes']['tableHeader']
                        elif reference and ri == 0 and config.get('referenceTypography',{}).get('enabled',True):
                            cell_size = reference.get('headerSize',size)
                        cell_height = sum(int(r.get('h'))/EMU for r in rows[ri:ri+int(cell.get('rowSpan','1'))])
                        if tcpr.get('vert') in ('vert','vert270','eaVert'):
                            ensure(body,q('a','bodyPr')).set('vert',tcpr.get('vert'))
                        measured = normalize_body(body, font, cell_size, role,
                          max(0.01, cell_height-2*padding), cell_width-gutter-padding, 0, False)
                        entry = {'slide': number, 'id': ident, 'cell': [ri, ci], 'role': role, 'preferredFontSize':preferred_size, 'resolvedFontSize':cell_size, 'typographyRole':'tableHeader' if ri == 0 and hierarchy.get('enabled') else role, **measured}
                        if int(cell.get('rowSpan', 1)) > 1:
                            entry['availableHeight'] = sum(int(r.get('h'))/EMU for r in rows[ri:ri+int(cell.get('rowSpan'))])-2*padding
                            entry['rowSpan'] = int(cell.get('rowSpan'))
                        table_records.append(entry)
                        if cell.get('rowSpan', '1') == '1':
                            required = max(required, measured['requiredHeight']+2*padding)
                    required_rows.append(max(0.18, required, header_layout.get('minHeight',0) if ri == 0 else 0))
                needed = sum(required_rows)
                available = box['h']
                if needed > available and box['y']+needed <= plan['contentBottom'] and not custom:
                    available = needed
                    apply_box(record, {'box': {**box, 'h': available}}, {}, dimensions)
                if needed <= available+0.01:
                    spare = max(0, available-needed)/len(rows)
                    heights = [h+spare for h in required_rows]
                    for row, h in zip(rows, heights):
                        row.set('h', str(round(h*EMU)))
                    for entry in table_records:
                        start = entry['cell'][0]
                        entry['availableHeight'] = sum(heights[start:start+entry.get('rowSpan', 1)])-2*padding
                if overlays:
                    plan.setdefault('tableOverlays',{})[ident] = anchor_table_overlays(scene,record,widths,overlays,dimensions,size,config.get('flow',{}).get('tableOverlayBaseline',0.25))
                vertical_labels = materialize_vertical_table_labels(root,record,dimensions,font,size)
                if vertical_labels:plan.setdefault('verticalTableLabels',{})[ident] = vertical_labels
                icon_settings = config.get('flow',{}).get('tableIcons',{}).get(f'{number}.{record["name"]}')
                if icon_settings:
                    from layout_constraints import anchor_table_icons
                    plan.setdefault('tableIcons',{})[record['name']] = anchor_table_icons(
                        scene,record,icon_settings,config['spacing']['tablePadding']/72,dimensions)
                for entry in table_records:
                    records.append(entry)
                    if entry['requiredHeight'] > entry['availableHeight']+0.045:
                        issues.append(entry)
            else:
                body = node.find('p:txBody', NS)
                if body is None:
                    continue
                padding = plan['insets'].get(ident, 0 if role in ('dense', 'note') else min(config['spacing']['padding'], 0.025))
                if level in ('coverTitle','sectionCoverTitle'):
                    for paragraph in list(body.findall('a:p',NS)):
                        if not text_of(paragraph).strip(): body.remove(paragraph)
                preferred_size = size
                if not locked:
                    size = fit_body_size(body,font,size,limits['min'],role,box['h'],box['w'],padding,config.get('fontFit',{}))
                else:
                    # Preserve reference run sizes (including superscripts) for original headings.
                    for pi, paragraph in enumerate(body.findall('a:p',NS)):
                        ref_paragraphs = reference.get('paragraphs',[]) if reference else []
                        ref = ref_paragraphs[min(pi,len(ref_paragraphs)-1)] if ref_paragraphs else {}
                        for ri, run in enumerate(paragraph.findall('a:r',NS)+paragraph.findall('a:fld',NS)):
                            prop = ensure(run,q('a','rPr'))
                            sizes = ref.get('runSizes',[]) if not custom and not hierarchy.get('enabled') else []
                            prop.set('sz',str(round((sizes[min(ri,len(sizes)-1)] if sizes else size)*100)))
                    if hierarchy.get('enabled'):
                        for prop in body.iter():
                            if prop.tag in (q('a','defRPr'),q('a','rPr'),q('a','endParaRPr')):
                                prop.set('sz',str(round(size*100)))
                # Short chart/diagram labels can gain width without stealing space
                # from the next label. Preserve their center when centered in XML.
                if not custom and role == 'dense' and ident not in plan.get('textBottom',{}) and not (node.find('p:spPr/a:solidFill',NS) is not None and box['h']>0.4) and len(text.strip()) <= 45 and '\n' not in text.strip():
                    pp = body.find('a:p/a:pPr', NS)
                    from layout_constraints import text_width, typography
                    _,bold,tracking = typography(body,size)
                    # endParaRPr is not part of visible text: its tracking does not apply.
                    visible = body.findall('a:p/a:r/a:rPr',NS)
                    tracking = max([float(p.get('spc',0))/100 for p in visible] or [0])
                    gutter = int(body.find('a:bodyPr',NS).get('lIns',0))/EMU
                    target_width = text_width(text.strip(),size,bold,tracking,METRICS)+gutter+0.025
                    if box['w'] < target_width < 2.3:
                        centered = pp is not None and pp.get('algn') == 'ctr'
                        left = box['x']-(target_width-box['w'])/2 if centered else box['x']
                        candidate = {**box, 'x': max(0, left), 'w': target_width}
                        clear = candidate['x']+target_width < dimensions['width']-0.2
                        for other in scene.values():
                            if other is record or other['effectiveTransform'] is None or not text_of(other['node']).strip() or other['node'].tag == q('p', 'grpSp'):
                                continue
                            peer = box_for(other['effectiveTransform'], other['parentMatrix'])
                            if min(peer['y']+peer['h'],candidate['y']+candidate['h'])-max(peer['y'],candidate['y']) > 0.02 and (peer['x'] >= box['x']+box['w']-0.01 or peer['x']+peer['w'] <= box['x']+0.01):
                                if min(candidate['x']+candidate['w'], peer['x']+peer['w'])-max(candidate['x'], peer['x']) > 0.001:
                                    clear = False
                        if clear:
                            box = candidate
                            apply_box(record, {'box': box}, {}, dimensions)
                measured = normalize_body(body, font, size, role, box['h'], box['w'], padding, locked or (custom and size == preferred_size), preserve_layout=not custom, paragraph_sizes=plan.get('paragraphSizes',{}).get(ident), paragraph_gap=plan.get('paragraphGaps',{}).get(ident,0), rich_measure=ident in plan.get('bodyMarkers',{}) or ident in plan.get('richText',{}))
                if not custom and measured['requiredHeight'] > box['h']+0.035:
                    # Grow only into clear space; never shrink below the selected floor.
                    desired = measured['requiredHeight']+0.02
                    limit = 7.35 if role == 'note' else plan.get('textBottom',{}).get(ident,plan['contentBottom'])
                    for other in scene.values():
                        if other is record or other['effectiveTransform'] is None or not text_of(other['node']).strip() or other['node'].tag == q('p', 'grpSp'):
                            continue
                        peer = box_for(other['effectiveTransform'], other['parentMatrix'])
                        overlap = min(box['x']+box['w'], peer['x']+peer['w'])-max(box['x'], peer['x'])
                        if overlap > min(box['w'], peer['w'])*0.4 and peer['y'] >= box['y']+box['h']-0.01:
                            limit = min(limit, peer['y']-0.03)
                    if box['y']+desired <= limit:
                        box = {**box, 'h': desired}
                        apply_box(record, {'box': box}, {}, dimensions)
                        measured = normalize_body(body, font, size, role, box['h'], box['w'], padding, locked or (custom and size == preferred_size), preserve_layout=not custom, paragraph_sizes=plan.get('paragraphSizes',{}).get(ident), paragraph_gap=plan.get('paragraphGaps',{}).get(ident,0), rich_measure=ident in plan.get('bodyMarkers',{}) or ident in plan.get('richText',{}))
                if ident in plan.get('bodyMarkers',{}):
                    from layout_constraints import anchor_paragraph_markers
                    anchor_paragraph_markers(root,scene,record,plan['bodyMarkers'][ident],measured['paragraphHeights'],dimensions,size)
                entry = {'slide': number, 'id': ident, 'name': record['name'], 'role': role,
                         'box': box, 'text': text[:100], 'preferredFontSize':preferred_size, 'resolvedFontSize':size, 'referenceLocked':locked, 'typographyRole':level or role, **measured}
                records.append(entry)
                if measured['requiredHeight'] > measured['availableHeight']+0.045:
                    issues.append(entry)
        parts[part] = xml_bytes(root)
    continuations = []
    for number, ident in config.get('paginate', [[5,'e9'],[8,'e5']]):
        if number not in selection or not any(e['slide']==number and e['id']==ident for e in issues):
            continue
        created, measures = paginate_narrative(parts, number, ident, config, dimensions, layout_plans[number]['contentBottom'])
        continuations.extend(created)
        issues = [e for e in issues if not (e['slide']==number and e['id']==ident)]
        records = [e for e in records if not (e['slide']==number and e['id']==ident)]+measures
    if continuations and 'docProps/app.xml' in parts:
        app = parse_xml(parts['docProps/app.xml'])
        for item in app.iter():
            if item.tag.endswith('}Slides'):
                item.text = str(len(selection)+len(continuations))
        parts['docProps/app.xml'] = xml_bytes(app)
    categories = complete_categories(parts, scale['dense'].get('size', scale['dense']['min']), font)
    from chart_compat import normalize_chart_workbooks
    workbook_repairs = normalize_chart_workbooks(parts)
    if issues and config.get('strict', True):
        refs = ', '.join(f"{item['slide']}.{item['id']}" for item in issues[:8])
        raise ValueError(f'Perfil quality: {len(issues)} textos não cabem nos mínimos; ajuste o layout: {refs}')
    return {'tokens': config, 'measuredObjects': len(records), 'measurements': records,
            'estimatedOverflow': issues, 'categoryRepairs': categories, 'workbookRepairs':workbook_repairs, 'continuations': continuations,
            'layoutConstraints':layout_plans, 'verification': 'Medição preventiva + revisão visual de exportação; não certifica todos os leitores Office.'}
