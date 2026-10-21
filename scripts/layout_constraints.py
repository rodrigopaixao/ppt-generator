"""Flow constraints: measured boxes, linked units and reserved footer space.

Distances use inches; fonts and tracking use points. This module repositions
editable drawings without rasterization or reader-dependent autofit."""
import re
import copy
import xml.etree.ElementTree as ET
from native_deck import (NS, EMU, q, scene_nodes, ancestors_for, box_for, text_of,
                         apply_box, ensure, parse_xml)


def text_width(text, size, bold, tracking, metrics):
    """Measure a line in inches using Arial advances and inter-character tracking."""
    face = metrics['widths']['bold' if bold else 'regular']
    return sum(face.get(c,0.55) for c in text)*size/72*1.04+max(0,len(text)-1)*tracking/72


def typography(node, size):
    """Read local/inherited bold and tracking from the text body's own list styles."""
    props = [p for p in node.iter() if p.tag in (q('a','rPr'),q('a','defRPr'))]
    return size, any(p.get('b')=='1' for p in props), max([float(p.get('spc',0))/100 for p in props] or [0])


def prepare_slide_layout(root, parts, part, config, dimensions):
    """Resolve bands, footer boundaries and stacks before normalizing text.

    Return effective bounds/insets and auditable adjustments. config.flow supplies
    padding/gap tokens and stacks with stable IDs. Elements linked to a row move
    together; insufficient space raises an error instead of allowing overlaps."""
    from quality_deck import METRICS, measure_lines
    flow = config.get('flow',{})
    if not flow.get('enabled',False):
        return {'contentBottom':6.8, 'insets':{}, 'adjustments':[]}
    ancestors = ancestors_for(parts,part)
    scene = scene_nodes(root,ancestors)
    adjustments = inset_container_text(scene,dimensions,flow.get('panelPadding',0.12),flow.get('boxPadding',0.06))
    insets = {change['id']:change.get('inset',0) for change in adjustments}
    number = int(part.rsplit('slide',1)[1].split('.')[0])
    boxes = {i:box_for(r['effectiveTransform'],r['parentMatrix']) for i,r in scene.items() if r['effectiveTransform'] is not None}
    size = config.get('hierarchy',{}).get('sizes',{}).get('kicker',10)
    pad = flow.get('boxPadding',0.06)
    tags = [i for i,r in scene.items() if i in boxes and boxes[i]['y']<0.05 and boxes[i]['h']<0.6 and boxes[i]['w']>0.5
            and text_of(r['node']).strip() and len(text_of(r['node']).strip())<70
            and r['node'].find('p:spPr/a:solidFill',NS) is not None]
    cursor = min([boxes[i]['x'] for i in tags] or [0])
    tag_height = size/72*1.1+2*pad
    for ident in sorted(tags,key=lambda i:boxes[i]['x']):
        node, old = scene[ident]['node'],boxes[ident]
        if config.get('hierarchy',{}).get('enabled'):
            config['hierarchy'].setdefault('roles',{}).setdefault(f'{number}.{ident}','kicker')
        _, bold, tracking = typography(node,size)
        width = text_width(text_of(node).strip(),size,bold,tracking,METRICS)+2*pad
        wraps = cursor+width > dimensions['width']-0.02
        if wraps:
            width = dimensions['width']-0.02-cursor
        height = max(tag_height,measure_lines(text_of(node),width-2*pad,size,bold,tracking)*size/72*1.1+2*pad)
        box = {**old,'x':cursor,'w':width,'h':height}
        apply_box(scene[ident],{'box':box},{},dimensions)
        body = node.find('p:txBody',NS)
        props = ensure(body,q('a','bodyPr'))
        props.set('wrap','square' if wraps else 'none')
        props.set('lIns',str(round(pad*EMU)));props.set('rIns',str(round(pad*EMU)))
        insets[ident] = pad
        boxes[ident] = box
        cursor += width
        adjustments.append({'id':ident,'constraint':'content-sized-band','box':box})
    footer = flow.get('footer',{})
    footer_top, footer_bottom = footer.get('top',6.8),footer.get('bottom',7.32)
    gap = footer.get('gap',0.14)
    notes = [i for i,r in scene.items() if i in boxes and boxes[i]['y']>6.4 and (
        re.match(r'^(?:\d+\.\s*)?(?:Source:|Sources:|Note:|Notes:)',text_of(r['node']).strip(),re.I)
        or (r['node'].find('p:nvSpPr/p:nvPr/p:ph',NS) is not None and r['node'].find('p:nvSpPr/p:nvPr/p:ph',NS).get('idx')=='11')
        or not r['name'].startswith('custom.') and boxes[i]['y']>=6.75 and boxes[i]['w']>8 and boxes[i]['h']<=0.6 and len(text_of(r['node']))>80)]
    logo_top = dimensions['height']
    # Follow the visibility chain: layouts can hide master shapes.
    active = [root]
    if root.get('showMasterSp')!='0':
        for _,parent in ancestors:
            active.append(parent)
            if parent.get('showMasterSp')=='0':
                break
    for parent in active:
        for r in scene_nodes(parent).values():
            if r['effectiveTransform'] is None or r['parentId']:
                continue
            b = box_for(r['effectiveTransform'],r['parentMatrix'])
            if b['x']>dimensions['width']-1 and b['y']>6.5 and b['h']>0.1 and not text_of(r['node']).strip():
                logo_top = min(logo_top,b['y'])
    has_footer = bool(notes) or logo_top<dimensions['height']
    for ident in notes:
        old = boxes[ident]
        width = min(dimensions['width']-config['spacing']['marginX']-0.2, dimensions['width']-1.15)-config['spacing']['marginX']
        height = measure_lines(text_of(scene[ident]['node']),width,config['type']['note']['size'])*config['type']['note']['size']/72*1.1+0.04
        footer_top = min(footer_top,footer_bottom-height-0.02)
        box = {'x':config['spacing']['marginX'],'y':footer_top+0.02,'w':width,'h':height}
        apply_box(scene[ident],{'box':box},{},dimensions)
        boxes[ident] = box
        adjustments.append({'id':ident,'constraint':'footer-note','box':box})
    auxiliary = [i for i,r in scene.items() if i in boxes and r['name'] in footer.get('auxiliary',{}).get(str(number),[])]
    for ident in auxiliary:
        old = boxes[ident]
        width = min(old['w'],dimensions['width']-1.15-old['x'])
        aux_size = config['type']['dense']['size']
        height = measure_lines(text_of(scene[ident]['node']),width,aux_size)*aux_size/72*1.1+0.04
        footer_top = min(footer_top,footer_bottom-height-0.02)
        box = {**old,'y':footer_top+0.02,'w':width,'h':height}
        apply_box(scene[ident],{'box':box},{},dimensions)
        boxes[ident] = box
        adjustments.append({'id':ident,'constraint':'footer-auxiliary','box':box})
    has_footer = has_footer or bool(auxiliary)
    content_bottom = min(footer_top,logo_top)-gap if has_footer else dimensions['height']-0.18
    # Measure and flow linked rows. Other drawings in the row keep their anchor.
    for stack in flow.get('stacks',{}).get(str(number),[]):
        row_gap = stack.get('gap',config['spacing']['gap'])
        ids = [i for i in stack['ids'] if i in scene and i in boxes]
        if not ids:
            continue
        records = [scene[i] for i in ids]
        old_rows = [boxes[i] for i in ids]
        heights = []
        for ident,r,b in zip(ids,records,old_rows):
            body = r['node'].find('p:txBody',NS)
            bp = ensure(body,q('a','bodyPr'))
            left = max(float(bp.get('lIns',0))/EMU,pad)
            font_size = config.get('hierarchy',{}).get('sizes',{}).get('component',12)
            _,bold,tracking = typography(r['node'],font_size)
            needed = measure_lines(text_of(r['node']),b['w']-left-pad,font_size,bold,tracking)*font_size/72*1.1+2*pad
            heights.append(needed)
        available = content_bottom-old_rows[0]['y']-row_gap*(len(ids)-1)
        if sum(heights)>available:
            raise ValueError(f'{number}: stack {ids} does not fit without overlap')
        desired = [max(b['h'],h) for b,h in zip(old_rows,heights)]
        ratio = min(1,(available-sum(heights))/max(0.0001,sum(desired)-sum(heights)))
        heights = [h+(d-h)*ratio for h,d in zip(heights,desired)]
        cursor = old_rows[0]['y']
        for ident,r,old,height in zip(ids,records,old_rows,heights):
            delta = cursor+height/2-(old['y']+old['h']/2)
            for peer,pr in scene.items():
                if peer not in boxes or pr['parentId'] or peer in ids:
                    continue
                b = boxes[peer]
                if b['x']>=old['x'] and b['x']<stack.get('right',8.7) and old['y']<=b['y']+b['h']/2<=old['y']+old['h']:
                    shifted = {**b,'y':b['y']+delta}
                    apply_box(pr,{'box':shifted},{},dimensions)
                    boxes[peer] = shifted
            box = {**old,'y':cursor,'h':height}
            apply_box(r,{'box':box},{},dimensions)
            boxes[ident] = box
            insets[ident] = pad
            ensure(r['node'].find('p:txBody',NS),q('a','bodyPr')).set('wrap','square')
            cursor += height+row_gap
            adjustments.append({'id':ident,'constraint':'linked-stack','box':box})
    own_logos = [i for i,r in scene.items() if i in boxes and not r['parentId'] and not text_of(r['node']).strip() and boxes[i]['x']>dimensions['width']-1 and boxes[i]['y']>6.5 and boxes[i]['h']>0.1]
    for ident,r in scene.items():
        if ident not in boxes or r['parentId'] or ident in notes or ident in auxiliary or ident in own_logos:
            continue
        box = boxes[ident]
        node = r['node']
        body = node.find('p:txBody',NS)
        # Vertical labels grow along their reading axis, never as stacked letters.
        if body is not None and ensure(body,q('a','bodyPr')).get('vert') in ('vert','vert270'):
            text = text_of(node).strip()
            font_size = config.get('hierarchy',{}).get('sizes',{}).get('component',config['type']['body']['size'])
            if config.get('hierarchy',{}).get('enabled'):
                config['hierarchy'].setdefault('roles',{}).setdefault(f'{number}.{ident}','component')
            _,bold,tracking = typography(node,font_size)
            height = max(box['h'],text_width(text,font_size,bold,tracking,METRICS)+2*pad)
            center = box['y']+box['h']/2
            box = {**box,'y':max(1.6,center-height/2),'h':height}
            ensure(body,q('a','bodyPr')).set('wrap','none')
            apply_box(r,{'box':box},{},dimensions)
            boxes[ident] = box
        if box['y']>=1.0 and box['y']+box['h']>content_bottom+0.001 and box['h']>=0:
            if box['h']>0.7 and box['y']<content_bottom-0.1:
                box = {**box,'h':content_bottom-box['y']}
            else:
                box = {**box,'y':min(box['y'],content_bottom-box['h'])}
            apply_box(r,{'box':box},{},dimensions)
            adjustments.append({'id':ident,'constraint':'footer-clearance','box':box})
    panel_plan = {'paragraphSizes':{},'textBottom':{i:boxes[i]['y']+boxes[i]['h'] for i in tags}}
    for ident,levels in flow.get('textHierarchy',{}).get(str(number),{}).items():
        panel_plan['paragraphSizes'][ident] = [config['hierarchy']['sizes'].get(level,config['type'].get(level,{}).get('size')) for level in levels]
        config.setdefault('roles',{})[f'{number}.{ident}'] = 'dense'
    if str(number) in flow.get('panels',{}):
        panel_plan = layout_panels(root,parts,part,flow['panels'][str(number)],config,dimensions,content_bottom)
        insets.update(panel_plan.pop('insets'))
        adjustments.extend(panel_plan.pop('adjustments'))
        legend = flow['panels'][str(number)].get('legend')
        if legend:
            layout_marker_legend(root,parts,part,legend,dimensions,footer_top)
            auxiliary.append(legend['group'])
    if str(number) in flow.get('cards',{}):
        card_plan = layout_cards(root,parts,part,flow['cards'][str(number)],config,dimensions,content_bottom)
        insets.update(card_plan.pop('insets'))
        adjustments.extend(card_plan.pop('adjustments'))
        for key,value in card_plan.items():
            panel_plan.setdefault(key,{}).update(value)
    if str(number) in flow.get('iconCards',{}):
        icon_plan = layout_icon_cards(root,parts,part,flow['iconCards'][str(number)],config,dimensions)
        insets.update(icon_plan.pop('insets'))
        adjustments.extend(icon_plan.pop('adjustments'))
        for key,value in icon_plan.items():
            panel_plan.setdefault(key,{}).update(value)
    review_plan = layout_review_regions(root,parts,part,config,dimensions,content_bottom)
    insets.update(review_plan.pop('insets'))
    adjustments.extend(review_plan.pop('adjustments'))
    for key,value in review_plan.items():
        panel_plan.setdefault(key,{}).update(value)
    return {**panel_plan,'contentBottom':content_bottom,'insets':insets,'adjustments':adjustments,'footerTop':footer_top if has_footer else None,'notes':notes,'footerElements':notes+auxiliary+own_logos}


def anchor_table_icons(scene, table_record, settings, padding, dimensions):
    """Anchor vector icons to final table geometry with a constant gap.

    scene contains pieces indexed by name. settings defines the reserved column,
    text column, name prefix and size/gap in inches. Center icons within each final
    row height; each piece retains its position relative to the background."""
    table = table_record['node'].find('.//a:tbl',NS)
    if table is None or settings.get('enabled',True) is False:
        return []
    bounds = box_for(table_record['effectiveTransform'],table_record['parentMatrix'])
    widths = [int(c.get('w'))/EMU for c in table.findall('a:tblGrid/a:gridCol',NS)]
    rows = table.findall('a:tr',NS)
    size, gap = settings['size'],settings['gap']
    text_column, icon_column = settings['textColumn'],settings['column']
    if size<=0 or gap<0 or not 0<=icon_column<text_column<len(widths):
        raise ValueError('Invalid size/gap or icon/text column order')
    x = bounds['x']+sum(widths[:text_column])+padding-gap-size
    column_left = bounds['x']+sum(widths[:icon_column])
    if x<column_left+padding-0.001:
        raise ValueError('Icon column cannot fit size + gap + padding')
    y = bounds['y']+int(rows[0].get('h'))/EMU
    anchors = []
    for index,row in enumerate(rows[1:],1):
        height = int(row.get('h'))/EMU
        if size+2*padding>height+0.001:
            raise ValueError(f'Icon in row {index} does not fit the final height')
        prefix = f"custom.{settings['prefix']}-{index}-"
        background = next((r for r in scene.values() if r['name']==prefix+'bg'),None)
        if background is not None:
            old = box_for(background['effectiveTransform'],background['parentMatrix'])
            target = {'x':x,'y':y+(height-size)/2,'w':size,'h':size}
            for record in scene.values():
                if not record['name'].startswith(prefix) or record['effectiveTransform'] is None:
                    continue
                local = box_for(record['effectiveTransform'],record['parentMatrix'])
                box = {'x':target['x']+(local['x']-old['x'])*size/old['w'],
                    'y':target['y']+(local['y']-old['y'])*size/old['h'],
                    'w':local['w']*size/old['w'],'h':local['h']*size/old['h']}
                apply_box(record,{'box':box},{},dimensions)
            anchors.append({'row':index,'box':target,'gap':gap,
                'textStart':bounds['x']+sum(widths[:text_column])+padding})
        y += height
    return anchors


def inset_container_text(scene, dimensions, padding, compact_padding=0.06):
    """Apply the same minimum inset to text contained in independent backgrounds.

    Choose the smallest filled background containing the entire box, preserving
    functional icon margins. Shapes with their own text and fill receive a text-body
    inset; independent backgrounds receive inner geometry. Return auditable changes
    with explicit insets to avoid applying padding twice."""
    adjustments = []
    backgrounds = []
    for r in scene.values():
        if r['effectiveTransform'] is None or text_of(r['node']).strip() or (r['node'].find('p:spPr/a:solidFill',NS) is None and r['node'].find('p:spPr/a:ln/a:solidFill',NS) is None):
            continue
        b = box_for(r['effectiveTransform'],r['parentMatrix'])
        if b['w']>=1 and 0.6<=b['h']<=6 and b['w']<=12.5:
            backgrounds.append((b,r))
    for ident,r in scene.items():
        if r['effectiveTransform'] is None or not text_of(r['node']).strip() or r['node'].tag!=q('p','sp'):
            continue
        b = box_for(r['effectiveTransform'],r['parentMatrix'])
        parents = [(p,pr) for p,pr in backgrounds if p['x']-.005<=b['x'] and p['y']-.005<=b['y'] and b['x']+b['w']<=p['x']+p['w']+.005 and b['y']+b['h']<=p['y']+p['h']+.005]
        own_fill = r['node'].find('p:spPr/a:solidFill',NS) is not None
        if own_fill or not parents:
            # A filled text shape is its own container, even inside another fill.
            # Shrinking its geometry would detach its background from peer rows.
            if (own_fill or r['node'].find('p:spPr/a:ln/a:solidFill',NS) is not None) and b['w']>=1 and 0.35<=b['h']<=6 and b['w']<=12.5:
                effective = compact_padding if b['h']<0.8 else padding
                adjustments.append({'id':ident,'constraint':'native-container-padding','padding':effective,'inset':effective,'box':b})
            continue
        parent,_ = min(parents,key=lambda p:p[0]['w']*p[0]['h'])
        x,y = max(b['x'],parent['x']+padding),max(b['y'],parent['y']+padding)
        right,bottom = min(b['x']+b['w'],parent['x']+parent['w']-padding),min(b['y']+b['h'],parent['y']+parent['h']-padding)
        if right>x and bottom>y:
            box = {'x':x,'y':y,'w':right-x,'h':bottom-y}
            apply_box(r,{'box':box},{},dimensions)
            adjustments.append({'id':ident,'constraint':'container-padding','padding':padding,'box':box})
    return adjustments


def layout_panels(root, parts, part, settings, config, dimensions, content_bottom):
    """Compose panels with common padding, icons, headings and a marker lane.

    settings.panels binds original background/header/body/icon IDs. Headings use the
    component token and descriptions use dense. Bodies start at the same height;
    lists drop duplicate bullets and reserve a separate marker lane."""
    from quality_deck import measure_lines
    scene = scene_nodes(root,ancestors_for(parts,part))
    padding, gap = settings['padding'],settings['gap']
    headers, header_sizes = [], []
    for panel in settings['panels']:
        r = scene[panel['header']]
        paragraphs = r['node'].findall('p:txBody/a:p',NS)
        sizes = [config['hierarchy']['sizes']['component'] if i==0 else config['type']['dense']['size'] for i in range(len(paragraphs))]
        background = scene[panel['background']]
        b = box_for(background['effectiveTransform'],background['parentMatrix'])
        h = sum(measure_lines(text_of(p),b['w']-2*padding,size,i==0)*size/72*1.1 for i,(p,size) in enumerate(zip(paragraphs,sizes)))
        headers.append(h+0.04)
        header_sizes.append(sizes)
    header_height = max(headers)
    result = {'paragraphSizes':{},'paragraphGaps':{},'bodyMarkers':{},'textBottom':{},'insets':{},'adjustments':[]}
    for panel,sizes in zip(settings['panels'],header_sizes):
        background = scene[panel['background']]
        b = box_for(background['effectiveTransform'],background['parentMatrix'])
        b['h'] = content_bottom-b['y']
        apply_box(background,{'box':b},{},dimensions)
        icon = scene[panel['icon'][0]]
        old = box_for(icon['effectiveTransform'],icon['parentMatrix'])
        dx,dy = b['x']+padding-old['x'],b['y']+padding-old['y']
        for ident in panel['icon']:
            r = scene[ident]; ib = box_for(r['effectiveTransform'],r['parentMatrix'])
            apply_box(r,{'box':{**ib,'x':ib['x']+dx,'y':ib['y']+dy}},{},dimensions)
        hy = b['y']+padding+old['h']+gap
        head = {'x':b['x']+padding,'y':hy,'w':b['w']-2*padding,'h':header_height}
        body = {'x':b['x']+padding+settings['markerLane']+settings['markerGap'],
            'y':hy+header_height+gap,'w':b['w']-2*padding-settings['markerLane']-settings['markerGap'],
            'h':b['y']+b['h']-padding-(hy+header_height+gap)}
        for ident,box in [(panel['header'],head),(panel['body'],body)]:
            apply_box(scene[ident],{'box':box},{},dimensions)
            result['insets'][ident] = 0
            result['adjustments'].append({'id':ident,'constraint':'padded-panel','padding':padding,'box':box})
        body_xml = scene[panel['body']]['node'].find('p:txBody',NS)
        ensure(body_xml,q('a','bodyPr')).set('wrap','square')
        for p in body_xml.findall('a:p',NS):
            pp = p.find('a:pPr',NS)
            if pp is None:
                pp = ensure(p,q('a','pPr'))
                p.remove(pp); p.insert(0,pp)
            pp.set('marL','0'); pp.set('indent','0')
            for child in list(pp):
                if child.tag.rsplit('}',1)[-1].startswith('bu'):
                    pp.remove(child)
            ensure(pp,q('a','buNone'))
        result['textBottom'][panel['body']] = b['y']+b['h']-padding
        result['textBottom'][panel['header']] = body['y']-gap
        result['paragraphSizes'][panel['header']] = sizes
        result['paragraphGaps'][panel['body']] = settings.get('paragraphGap',0.04)
        result['bodyMarkers'][panel['body']] = {'ids':panel['markers'],'x':b['x']+padding,'lane':settings['markerLane'],'size':settings['markerSize']}
    if settings.get('labels'):
        first = scene[settings['panels'][0]['background']]
        background_box = box_for(first['effectiveTransform'],first['parentMatrix'])
        x = config['spacing']['marginX']
        width = background_box['x']-gap-x
        for key,box in [('header',{'x':x,'y':head['y'],'w':width,'h':head['h']}),
                        ('body',{'x':x,'y':body['y'],'w':width,'h':min(1,body['h'])})]:
            ident = settings['labels'][key]
            apply_box(scene[ident],{'box':box},{},dimensions)
            result['insets'][ident] = 0
    return result


def anchor_paragraph_markers(root, scene, body_record, settings, heights, dimensions, font_size):
    """Reposition circles/groups on the first line of each measured paragraph."""
    box = box_for(body_record['effectiveTransform'],body_record['parentMatrix'])
    y = box['y']
    for index,ident in enumerate(settings['ids']):
        record = scene[ident]
        old = box_for(record['effectiveTransform'],record['parentMatrix'])
        dual = record['node'].tag==q('p','grpSp')
        size = settings['size']
        height = size*2+0.02 if dual else size
        target = {'x':settings['x']+(settings['lane']-size)/2,'y':y+(font_size/72*1.1-height)/2,'w':size,'h':height}
        apply_box(record,{'box':target},{},dimensions)
        if dual:
            # Preserve circular dots even when the enclosing group changes aspect.
            updated = scene_nodes(root)
            children = [r for r in updated.values() if r['parentId']==ident]
            for child_index,child in enumerate(children):
                apply_box(child,{'box':{'x':target['x'],'y':target['y']+child_index*(size+0.02),'w':size,'h':size}},{},dimensions)
        y += heights[index] if index<len(heights) else 0


def layout_marker_legend(root, parts, part, settings, dimensions, footer_top):
    """Align legend markers and labels with a constant gap before the logo."""
    scene = scene_nodes(root,ancestors_for(parts,part))
    size,gap,label_width,item_gap = 0.09,0.08,0.65,0.25
    width = len(settings['items'])*(size+gap+label_width)+(len(settings['items'])-1)*item_gap
    x,y = dimensions['width']-1.15-width,footer_top+0.02
    apply_box(scene[settings['group']],{'box':{'x':x,'y':y,'w':width,'h':0.22}},{},dimensions)
    scene = scene_nodes(root,ancestors_for(parts,part))
    for marker,label in settings['items']:
        apply_box(scene[marker],{'box':{'x':x,'y':y+(0.22-size)/2,'w':size,'h':size}},{},dimensions)
        apply_box(scene[label],{'box':{'x':x+size+gap,'y':y,'w':label_width,'h':0.22}},{},dimensions)
        x += size+gap+label_width+item_gap


def layout_cards(root, parts, part, settings, config, dimensions, content_bottom):
    """Distribute native cards in reading order with common padding and gaps.

    settings binds group/title/badge/body/owner IDs. Distances use inches; fonts use
    central hierarchy tokens in points. Measure headings and owner names before
    placement: names gain height per line and align at the bottom. Titles share the
    native background, so their left inset reserves a badge lane. Recompute group
    matrices after each change. Fail if minimum text, padding and gaps do not fit."""
    from quality_deck import measure_lines
    scene = scene_nodes(root,ancestors_for(parts,part))
    grid = box_for(scene[settings['group']]['effectiveTransform'],scene[settings['group']]['parentMatrix'])
    pad,compact,gap = settings['padding'],settings['compactPadding'],settings['gap']
    inner,badge = settings['internalGap'],settings['badgeSize']
    columns = settings['columns']; rows = (len(settings['cards'])+columns-1)//columns
    banner = {**grid,'y':settings['bannerTop'],'h':settings['bannerHeight']}
    apply_box(scene[settings['bannerGroup']],{'box':banner},{},dimensions)
    top = banner['y']+banner['h']+gap
    grid = {**grid,'y':top,'h':content_bottom-top}
    apply_box(scene[settings['group']],{'box':grid},{},dimensions)
    scene = scene_nodes(root,ancestors_for(parts,part))
    width = (grid['w']-(columns-1)*gap)/columns
    height = (grid['h']-(rows-1)*gap)/rows
    boxes = []
    for index,card in enumerate(settings['cards']):
        box = {'x':grid['x']+(index%columns)*(width+gap),'y':top+(index//columns)*(height+gap),'w':width,'h':height}
        boxes.append(box)
        apply_box(scene[card['group']],{'box':box},{},dimensions)
    scene = scene_nodes(root,ancestors_for(parts,part))
    section = config['hierarchy']['sizes']['section']; dense = config['type']['dense']['size']
    heading_heights = []
    for card in settings['cards']:
        _,bold,tracking = typography(scene[card['title']]['node'],section)
        heading_heights.append(measure_lines(text_of(scene[card['title']]['node']),width-2*pad-badge-settings['badgeGap'],section,bold,tracking)*section/72*1.1)
    header = max(badge,max(heading_heights))
    result = {'insets':{},'adjustments':[],'textBottom':{},'paragraphSizes':{settings['banner']:[section,dense]}}
    result['insets'][settings['banner']] = compact
    number = int(part.rsplit('slide',1)[1].split('.')[0])
    for card,box in zip(settings['cards'],boxes):
        title = scene[card['title']]
        apply_box(title,{'box':box},{},dimensions)
        props = ensure(title['node'].find('p:txBody',NS),q('a','bodyPr'))
        props.set('anchor','t');props.set('lIns',str(round((pad+badge+settings['badgeGap'])*EMU)))
        result['insets'][card['title']] = pad
        config['hierarchy'].setdefault('roles',{})[f"{number}.{card['title']}"] = 'section'
        badge_box = {'x':box['x']+pad,'y':box['y']+pad,'w':badge,'h':badge}
        apply_box(scene[card['badge']],{'box':badge_box},{},dimensions)
        result['insets'][card['badge']] = 0
        ensure(scene[card['badge']]['node'].find('p:txBody',NS),q('a','bodyPr')).set('anchor','ctr')
        owner_heights = [measure_lines(text_of(scene[ident]['node']),width-2*pad-2*compact,dense,True)*dense/72*1.1+2*compact for ident in card['owners']]
        owner_top = box['y']+height-pad-sum(owner_heights)-inner*(len(owner_heights)-1)
        body_top = box['y']+pad+header+inner
        body_height = owner_top-inner-body_top
        needed = measure_lines(text_of(scene[card['body']]['node']),width-2*pad,dense)*dense/72*1.1
        if needed>body_height+0.005:
            raise ValueError(f"Card {number}.{card['title']}: text requires {needed:.3f} in; available {body_height:.3f} in")
        body_box = {'x':box['x']+pad,'y':body_top,'w':width-2*pad,'h':body_height}
        apply_box(scene[card['body']],{'box':body_box},{},dimensions)
        ensure(scene[card['body']]['node'].find('p:txBody',NS),q('a','bodyPr')).set('anchor','t')
        result['insets'][card['body']] = 0
        result['textBottom'][card['body']] = owner_top-inner
        for ident,owner_height in zip(card['owners'],owner_heights):
            owner_box = {'x':box['x']+pad,'y':owner_top,'w':width-2*pad,'h':owner_height}
            apply_box(scene[ident],{'box':owner_box},{},dimensions)
            props = ensure(scene[ident]['node'].find('p:txBody',NS),q('a','bodyPr'))
            props.set('anchor','ctr');props.set('lIns',str(round(compact*EMU)))
            result['insets'][ident] = compact
            config['hierarchy']['roles'][f'{number}.{ident}'] = 'chartTitle'
            owner_top += owner_height+inner
        result['adjustments'].append({'id':card['title'],'constraint':'padded-card','padding':pad,'compactPadding':compact,'gap':inner,'box':box})
    return result


def layout_icon_cards(root, parts, part, settings, config, dimensions):
    """Separate backgrounds, headings and native card lists with icons above text.

    settings.cards supplies body (the original shape with fill and all paragraphs)
    and icon (background plus vector drawing, or an entire group). headingParagraphs
    counts the initial nonempty heading paragraphs. padding/gap/paragraphGap/iconSize
    use inches. Preserve original paragraphs and bullets; duplicate only editable
    shapes with new IDs. Measure the tallest heading using component points to align
    all lists. Dense bodies use the remaining space without entering icon/footer areas."""
    from quality_deck import measure_lines
    scene = scene_nodes(root,ancestors_for(parts,part))
    padding,gap = settings['padding'],settings['gap']
    size = config['hierarchy']['sizes']['component']
    next_id = max(int(i[1:]) for i in scene if i[1:].isdigit())+1
    number = int(part.rsplit('slide',1)[1].split('.')[0])
    result = {'insets':{},'adjustments':[],'paragraphGaps':{},'textBottom':{}}
    cards = []
    for card in settings['cards']:
        original = scene[card['body']]
        box = box_for(original['effectiveTransform'],original['parentMatrix'])
        body = original['node'].find('p:txBody',NS)
        paragraphs = body.findall('a:p',NS)
        for paragraph in list(paragraphs):
            if not text_of(paragraph).strip(): body.remove(paragraph)
        paragraphs = body.findall('a:p',NS)
        titles = paragraphs[:card.get('headingParagraphs',1)]
        title_height = sum(measure_lines(text_of(title),box['w']-2*padding,size,True)*size/72*1.1 for title in titles)
        cards.append((card,box,title_height))
        # The background fills the entire card without carrying text or insets.
        background = copy.deepcopy(original['node'])
        background.remove(background.find('p:txBody',NS))
        identity = background.find('p:nvSpPr/p:cNvPr',NS)
        identity.set('id',str(next_id)); identity.set('name',f'flow.card-background-{card["body"]}')
        for extension in list(identity): identity.remove(extension)
        next_id += 1
        original['parent'].insert(list(original['parent']).index(original['node']),background)
        heading = copy.deepcopy(original['node'])
        heading_body = heading.find('p:txBody',NS)
        for paragraph in heading_body.findall('a:p',NS): heading_body.remove(paragraph)
        for title in titles: heading_body.append(copy.deepcopy(title))
        identity = heading.find('p:nvSpPr/p:cNvPr',NS)
        heading_id = f'e{next_id}'
        identity.set('id',str(next_id));identity.set('name',f'flow.card-title-{card["body"]}')
        for extension in list(identity): identity.remove(extension)
        next_id += 1
        original['parent'].insert(list(original['parent']).index(original['node']),heading)
        for title in titles: body.remove(title)
        for paragraph in list(body.findall('a:p',NS)):
            if not text_of(paragraph).strip(): body.remove(paragraph)
        for node in [heading,original['node']]:
            properties = node.find('p:spPr',NS)
            for child in list(properties):
                if child.tag.rsplit('}',1)[-1] in ('solidFill','gradFill','blipFill','pattFill','grpFill','noFill'):
                    properties.remove(child)
            properties.insert(2, ET.Element(q('a','noFill')))
            props = ensure(node.find('p:txBody',NS),q('a','bodyPr'))
            props.set('lIns','0');props.set('rIns','0');props.set('anchor','t')
        card = {**card,'heading':heading_id}
        cards[-1] = (card,box,title_height)
        config['hierarchy'].setdefault('roles',{})[f'{number}.{heading_id}'] = 'component'
        config.setdefault('roles',{})[f'{number}.{card["body"]}'] = 'dense'
    scene = scene_nodes(root,ancestors_for(parts,part))
    common_header = max(height for _,_,height in cards)+0.02
    for card,box,_ in cards:
        icon = scene[card['icon'][0]]
        old_icon = box_for(icon['effectiveTransform'],icon['parentMatrix'])
        icon_size = settings['iconSize']
        for ident in card['icon']:
            record = scene[ident]
            old = box_for(record['effectiveTransform'],record['parentMatrix'])
            scale = icon_size/old_icon['w']
            target = {'x':box['x']+padding+(old['x']-old_icon['x'])*scale,
                      'y':box['y']+padding+(old['y']-old_icon['y'])*scale,
                      'w':old['w']*scale,'h':old['h']*scale}
            apply_box(record,{'box':target},{},dimensions)
        title_y = box['y']+padding+icon_size+gap
        title_box = {'x':box['x']+padding,'y':title_y,'w':box['w']-2*padding,'h':common_header}
        body_y = title_y+common_header+gap
        body_box = {**title_box,'y':body_y,'h':box['y']+box['h']-padding-body_y}
        if body_box['h']<=0: raise ValueError(f'Card {number}.{card["body"]} has no usable space')
        for ident,target in [(card['heading'],title_box),(card['body'],body_box)]:
            apply_box(scene[ident],{'box':target},{},dimensions)
            result['insets'][ident] = 0
            result['textBottom'][ident] = target['y']+target['h']
        result['paragraphGaps'][card['body']] = settings['paragraphGap']
        result['adjustments'].append({'id':card['body'],'heading':card['heading'],'constraint':'icon-before-card-text','padding':padding,'gap':gap,'box':box,'titleBox':title_box,'bodyBox':body_box})
    return result


def layout_review_regions(root, parts, part, config, dimensions, content_bottom):
    """Apply linked regions after general flow and before font normalization.

    flow.regions[slide] uses stable IDs, inch-based boxes and local inset/bottom values.
    compact removes only empty paragraphs; paragraphs assigns per-paragraph tokens.
    calloutRows links borders, text and icons using a shared measured height and
    constant padding/gaps. legends links inline markers and labels. numbered places
    badges on the first measured paragraph line in a dedicated lane. All objects
    remain editable DrawingML rather than text images."""
    from quality_deck import measure_rich_lines, METRICS
    number = part.rsplit('slide',1)[1].split('.')[0]
    settings = config.get('flow',{}).get('regions',{}).get(number,{})
    scene = scene_nodes(root,ancestors_for(parts,part))
    result = {'insets':{},'adjustments':[],'paragraphSizes':{},'paragraphGaps':{},'textBottom':{},'richText':{},'bodyMarkers':{},'preferredFontSizes':{}}
    for ident,region in settings.get('elements',{}).items():
        record = scene[ident];box = box_for(record['effectiveTransform'],record['parentMatrix'])
        box.update(region.get('box',{}))
        apply_box(record,{'box':box},{},dimensions)
        body = record['node'].find('p:txBody',NS)
        if body is not None and region.get('splitSoftBreaks'):
            # Promote title/body soft breaks to paragraphs so hierarchy tokens
            # can style each section independently without changing the words.
            for paragraph in list(body.findall('a:p',NS)):
                if paragraph.find('a:br',NS) is None:continue
                position = list(body).index(paragraph);body.remove(paragraph)
                props = paragraph.find('a:pPr',NS)
                current = ET.Element(q('a','p'))
                if props is not None:current.append(copy.deepcopy(props))
                for child in paragraph:
                    if child.tag == q('a','pPr'):continue
                    if child.tag == q('a','br'):
                        body.insert(position,current);position += 1;current = ET.Element(q('a','p'))
                        if props is not None:current.append(copy.deepcopy(props))
                    else:current.append(copy.deepcopy(child))
                body.insert(position,current)
        if body is not None and region.get('compact'):
            for paragraph in list(body.findall('a:p',NS)):
                if not text_of(paragraph).strip():body.remove(paragraph);continue
                # Leading soft breaks are invisible to text_of but Keynote honors them.
                for child in list(paragraph):
                    if child.tag==q('a','pPr'):continue
                    if child.tag==q('a','br') or child.tag==q('a','r') and not ''.join(t.text or '' for t in child.iter(q('a','t'))).strip():paragraph.remove(child)
                    else:break
        if body is not None:
            if 'leftInset' in region:ensure(body,q('a','bodyPr')).set('lIns',str(round(region['leftInset']*EMU)))
            if 'tracking' in region:
                for prop in body.iter():
                    if prop.tag in (q('a','rPr'),q('a','defRPr')):prop.set('spc',str(round(region['tracking']*100)))
            if region.get('trimLeading'):
                for paragraph in body.findall('a:p',NS):
                    text_node = next((t for t in paragraph.iter(q('a','t')) if (t.text or '').strip()),None)
                    if text_node is not None:text_node.text = text_node.text.lstrip()
            if 'anchor' in region:ensure(body,q('a','bodyPr')).set('anchor',region['anchor'])
            if 'align' in region:
                for paragraph in body.findall('a:p',NS):ensure(paragraph,q('a','pPr')).set('algn',region['align'])
        if 'inset' in region:result['insets'][ident] = region['inset']
        if region.get('paragraphs'):
            result['paragraphSizes'][ident] = [config['hierarchy']['sizes'].get(level,config['type'].get(level,{}).get('size')) for level in region['paragraphs']]
        if 'fontSize' in region:result['preferredFontSizes'][ident] = region['fontSize']
        if region.get('role'):config.setdefault('roles',{})[f'{number}.{ident}'] = region['role']
        if region.get('rich'):result['richText'][ident] = True
        if 'paragraphGap' in region:result['paragraphGaps'][ident] = region['paragraphGap']
        result['textBottom'][ident] = min(content_bottom,region.get('bottom',box['y']+box['h']))
        result['adjustments'].append({'id':ident,'constraint':'bounded-region','box':box})
    # Equivalent descriptions share the smallest fitted size required by a peer.
    from quality_deck import fit_body_size
    for ids in settings.get('fontGroups',[]):
        fitted = []
        for ident in ids:
            record = scene[ident];box = box_for(record['effectiveTransform'],record['parentMatrix'])
            role = config.get('roles',{}).get(f'{number}.{ident}','dense');limits = config['type'][role]
            fitted.append(fit_body_size(record['node'].find('p:txBody',NS),config['font'],
                result['preferredFontSizes'].get(ident,limits['size']),limits['min'],role,
                box['h'],box['w'],result['insets'].get(ident,0),config.get('fontFit',{}),rich_measure=True))
        for ident in ids:result['preferredFontSizes'][ident] = min(fitted)
    for stack in settings.get('calloutRows',[]):
        pad,gap = stack['padding'],stack['gap']
        height = (content_bottom-stack['top']-gap*(len(stack['rows'])-1))/len(stack['rows'])
        cursor = stack['top']
        for row in stack['rows']:
            background = scene[row['background']]
            old = box_for(background['effectiveTransform'],background['parentMatrix'])
            box = {**old,'y':cursor,'h':height}
            apply_box(background,{'box':box},{},dimensions)
            icon = scene[row['icon'][0]];ib = box_for(icon['effectiveTransform'],icon['parentMatrix'])
            dy = cursor+height/2-(ib['y']+ib['h']/2)
            for ident in row['icon']:
                r = scene[ident];b = box_for(r['effectiveTransform'],r['parentMatrix'])
                apply_box(r,{'box':{**b,'y':b['y']+dy}},{},dimensions)
            # Preserve the horizontal icon lane, with the standard gap to its right.
            x = max(box['x']+pad,ib['x']+ib['w']+pad)
            text_box = {'x':x,'y':cursor+pad,'w':box['x']+box['w']-pad-x,'h':height-2*pad}
            node = scene[row['text']]['node']
            body = node.find('p:txBody',NS)
            needed = sum(measure_rich_lines(p,text_box['w'],config['type']['body']['size'])*config['type']['body']['size']/72*1.1 for p in body.findall('a:p',NS))
            if needed>text_box['h']+0.005:raise ValueError(f'{number}.{row["text"]}: callout has no usable space')
            props = ensure(body,q('a','bodyPr'));props.set('lIns','0');props.set('rIns','0');props.set('anchor','ctr')
            apply_box(scene[row['text']],{'box':text_box},{},dimensions)
            result['insets'][row['text']] = 0;result['textBottom'][row['text']] = text_box['y']+text_box['h'];result['richText'][row['text']] = True
            config.setdefault('roles',{})[f'{number}.{row["text"]}'] = 'body'
            result['adjustments'].append({'id':row['text'],'constraint':'bounded-callout','padding':pad,'box':text_box,'container':box})
            cursor += height+gap
    for legend in settings.get('legends',[]):
        widths = [text_width(text_of(scene[item['label']]['node']).strip(),config['type']['dense']['size'],False,0,METRICS) for item in legend['items']]
        cursor = legend['right']-sum(widths)-len(widths)*(legend['size']+legend['gap'])-(len(widths)-1)*legend['itemGap']
        for item,width in zip(legend['items'],widths):
            mb = {'x':cursor,'y':legend['y'],'w':legend['size'],'h':legend['size']}
            lb = {'x':cursor+legend['size']+legend['gap'],'y':legend['y'],'w':width,'h':0.2}
            for ident,box in [(item['marker'],mb),(item['label'],lb)]:apply_box(scene[ident],{'box':box},{},dimensions)
            result['insets'][item['label']] = 0;result['textBottom'][item['label']] = lb['y']+lb['h']
            config.setdefault('roles',{})[f'{number}.{item["label"]}'] = 'dense'
            result['adjustments'].append({'id':item['label'],'constraint':'legend-clearance','marker':mb,'box':lb,'gap':legend['gap']})
            cursor = lb['x']+lb['w']+legend['itemGap']
    for ident,markers in settings.get('numbered',{}).items():
        body = scene[ident]['node'].find('p:txBody',NS)
        for paragraph in body.findall('a:p',NS):
            pp = ensure(paragraph,q('a','pPr'));pp.set('marL','0');pp.set('indent','0')
            for child in list(pp):
                if child.tag.rsplit('}',1)[-1].startswith('bu'):pp.remove(child)
            ensure(pp,q('a','buNone'))
        result['bodyMarkers'][ident] = markers
    return result


def table_overlay_cells(scene, record, widths):
    """Bind native value outlines to original table cells before reflow.

    Only unfilled rectangles without text and with a colored line inside the table
    qualify. Store row/column and outline size rather than fixed y positions.
    Highlights follow the final row distribution."""
    box = box_for(record['effectiveTransform'],record['parentMatrix'])
    table = record['node'].find('.//a:tbl',NS)
    heights = [int(row.get('h'))/EMU for row in table.findall('a:tr',NS)]
    found = []
    for ident,peer in scene.items():
        node = peer['node']
        if peer['effectiveTransform'] is None or text_of(node).strip() or node.find('p:spPr/a:ln/a:solidFill',NS) is None or node.find('p:spPr/a:solidFill',NS) is not None:continue
        geom = node.find('p:spPr/a:prstGeom',NS)
        if geom is None or geom.get('prst')!='rect':continue
        b = box_for(peer['effectiveTransform'],peer['parentMatrix'])
        if not (0.1<b['w']<1.5 and 0.05<b['h']<0.5 and box['x']<=b['x'] and b['x']+b['w']<=box['x']+box['w']+0.01 and box['y']<=b['y'] and b['y']+b['h']<=box['y']+sum(heights)+0.01):continue
        center_x,center_y = b['x']+b['w']/2,b['y']+b['h']/2
        x,y = box['x'],box['y'];column,row = None,None
        for i,width in enumerate(widths):
            if x<=center_x<x+width:column=i;break
            x+=width
        for i,height in enumerate(heights):
            if y<=center_y<y+height:row=i;break
            y+=height
        if row is not None and column is not None:found.append({'id':ident,'row':row,'column':column,'box':b})
    return found


def anchor_table_overlays(scene, record, widths, overlays, dimensions, font_size, baseline_fraction=0.25):
    """Anchor final outlines with optical baseline compensation in em fractions.

    Text lines reserve descenders, so visible digit centers sit below the line center.
    baseline_fraction compensates without moving table data or borders. The default
    0.25 em offset was checked in Keynote."""
    table = record['node'].find('.//a:tbl',NS)
    heights = [int(row.get('h'))/EMU for row in table.findall('a:tr',NS)]
    b = box_for(record['effectiveTransform'],record['parentMatrix']);result=[]
    for overlay in overlays:
        row,column = overlay['row'],overlay['column']
        width = min(overlay['box']['w'],widths[column]-0.04)
        height = min(heights[row]-0.02,max(overlay['box']['h'],font_size/72*1.1+0.04))
        target = {'x':b['x']+sum(widths[:column])+(widths[column]-width)/2,
                  'y':b['y']+sum(heights[:row])+(heights[row]-height)/2+font_size/72*baseline_fraction,'w':width,'h':height}
        apply_box(scene[overlay['id']],{'box':target},{},dimensions)
        result.append({**overlay,'box':target})
    return result


def materialize_vertical_table_labels(root, record, dimensions, font, font_size):
    """Keep vertical labels editable in readers that ignore table cell rotation.

    Keynote ignores tcPr@vert and wraps Tailwinds/Loans character by character. Move
    those cells' content to native text boxes rotated 270 degrees over the same area.
    Keep fills and merges in the table without duplicating text. Measure positions
    after distributing final row heights."""
    scene = scene_nodes(root);next_id = max(int(i[1:]) for i in scene if i[1:].isdigit())+1
    table = record['node'].find('.//a:tbl',NS);rows = table.findall('a:tr',NS)
    widths = [int(column.get('w'))/EMU for column in table.findall('a:tblGrid/a:gridCol',NS)]
    heights = [int(row.get('h'))/EMU for row in rows]
    bounds = box_for(record['effectiveTransform'],record['parentMatrix']);result=[]
    for ri,row in enumerate(rows):
        for ci,cell in enumerate(row.findall('a:tc',NS)):
            props = cell.find('a:tcPr',NS);body = cell.find('a:txBody',NS)
            if props is None or props.get('vert') not in ('vert','vert270') or body is None or not text_of(body).strip() or cell.get('vMerge')=='1' or cell.get('hMerge')=='1':continue
            visual = {'x':bounds['x']+sum(widths[:ci]),'y':bounds['y']+sum(heights[:ri]),
                'w':sum(widths[ci:ci+int(cell.get('gridSpan','1'))]),'h':sum(heights[ri:ri+int(cell.get('rowSpan','1'))])}
            text = text_of(body).strip();shape = ET.Element(q('p','sp'));nv = ET.SubElement(shape,q('p','nvSpPr'))
            ET.SubElement(nv,q('p','cNvPr'),id=str(next_id),name=f'flow.vertical-table-{record["id"]}-{ri}-{ci}');next_id+=1
            ET.SubElement(nv,q('p','cNvSpPr'),txBox='1');ET.SubElement(nv,q('p','nvPr'))
            sp = ET.SubElement(shape,q('p','spPr'));xf = ET.SubElement(sp,q('a','xfrm'),rot='16200000' if props.get('vert')=='vert270' else '5400000')
            ET.SubElement(xf,q('a','off'),x='0',y='0');ET.SubElement(xf,q('a','ext'),cx='1',cy='1')
            ET.SubElement(ET.SubElement(sp,q('a','prstGeom'),prst='rect'),q('a','avLst'));ET.SubElement(sp,q('a','noFill'));ET.SubElement(ET.SubElement(sp,q('a','ln')),q('a','noFill'))
            target_body = ET.SubElement(shape,q('p','txBody'));ET.SubElement(target_body,q('a','bodyPr'),anchor='ctr',lIns='0',rIns='0',tIns='0',bIns='0',wrap='none');ET.SubElement(target_body,q('a','lstStyle'))
            paragraph = ET.SubElement(target_body,q('a','p'));ET.SubElement(paragraph,q('a','pPr'),algn='ctr');run = ET.SubElement(paragraph,q('a','r'))
            original = body.find('a:p/a:r/a:rPr',NS);rpr = copy.deepcopy(original) if original is not None else ET.Element(q('a','rPr'))
            rpr.set('sz',str(round(font_size*100)));ensure(rpr,q('a','latin')).set('typeface',font);run.append(rpr);ET.SubElement(run,q('a','t')).text = text
            record['parent'].append(shape)
            fresh = scene_nodes(root)[f'e{next_id-1}']
            rotated = {'x':visual['x']+(visual['w']-visual['h'])/2,'y':visual['y']+(visual['h']-visual['w'])/2,'w':visual['h'],'h':visual['w']}
            apply_box(fresh,{'box':rotated},{},dimensions)
            for paragraph in body.findall('a:p',NS):body.remove(paragraph)
            ET.SubElement(body,q('a','p'));props.set('vert','horz');ensure(body,q('a','bodyPr')).set('vert','horz')
            result.append({'id':f'e{next_id-1}','text':text,'visualBox':visual,'fontSize':font_size})
    return result


def anchor_table_bars(scene, record, settings, dimensions):
    """Center linked timeline bars in final rows and constrain them to a column.

    settings.column is zero-based. items binds each semantic object name to a
    one-based data-row index (header is row zero). X spans retain source timing;
    vertical anchors are recomputed only after table row heights are finalized.
    """
    table = record['node'].find('.//a:tbl',NS)
    bounds = box_for(record['effectiveTransform'],record['parentMatrix'])
    widths = [int(c.get('w'))/EMU for c in table.findall('a:tblGrid/a:gridCol',NS)]
    heights = [int(r.get('h'))/EMU for r in table.findall('a:tr',NS)]
    column = settings['column'];left = bounds['x']+sum(widths[:column]);right = left+widths[column]
    by_name = {r['name']:r for r in scene.values()}
    anchors = []
    for item in settings['items']:
        target = by_name[item['name']];row = item['row']
        box = box_for(target['effectiveTransform'],target['parentMatrix'])
        x = max(left,box['x']);end = min(right,box['x']+box['w'])
        box = {**box,'x':x,'w':end-x,'y':bounds['y']+sum(heights[:row])+(heights[row]-box['h'])/2}
        if box['w']<=0 or box['h']>heights[row]:raise ValueError('Timeline bar exceeds its owning cell')
        apply_box(target,{'box':box},{},dimensions)
        anchors.append({'name':item['name'],'row':row,'box':box,'rowCenter':bounds['y']+sum(heights[:row])+heights[row]/2})
    return anchors
