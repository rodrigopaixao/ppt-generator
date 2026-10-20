"""Workbooks OOXML portáveis para os gráficos editáveis, inclusive no Keynote.

O perfil quality conserva séries, caches, estilos e fórmulas do gráfico. Corrige
os ranges XLSX emitidos por PptxGenJS 4.0.1 e oferece XLSX no lugar de XLSB para
importadores que não leem a planilha binária. Não rasteriza os gráficos.
"""
import io
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from native_deck import NS, q, parse_xml, xml_bytes, rel_path, add_content_type

S = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'


def column_index(label):
    """Converte uma coluna Excel A–XFD em inteiro base um, sem dependências."""
    result = 0
    for char in label:result = result*26+ord(char)-64
    return result


def column_name(index):
    """Converte índice base um em letras Excel, para endereçar células XLSX."""
    result = ''
    while index:
        index,digit = divmod(index-1,26);result = chr(65+digit)+result
    return result


def cached_cells(chart):
    """Lê fórmulas e caches em células por sheet, preservando pontos esparsos.

    O mapa resultante é {sheet: {(linha,coluna): (valor,é_número)}}. As fórmulas
    originais de c:numRef/c:strRef não são alteradas. Ranges retangulares seguem
    ordem por linha; não cria zeros onde a referência original não tem pontos.
    """
    sheets = {}
    for reference in list(chart.iter(q('c','numRef')))+list(chart.iter(q('c','strRef'))):
        formula = reference.findtext('c:f',namespaces=NS) or ''
        match = re.fullmatch(r"(?:'((?:[^']|'')+)'|([^!]+))!\$?([A-Z]+)\$?(\d+)(?::\$?([A-Z]+)\$?(\d+))?",formula)
        if not match:raise ValueError(f'Referência de workbook não suportada: {formula}')
        quoted,plain,start_col,start_row,end_col,end_row = match.groups()
        sheet = (quoted or plain).replace("''", "'")
        start = column_index(start_col);width = column_index(end_col or start_col)-start+1
        if width<1:raise ValueError(f'Range invertido: {formula}')
        cells = sheets.setdefault(sheet,{})
        cache = reference.find('c:numCache',NS) if reference.tag==q('c','numRef') else reference.find('c:strCache',NS)
        if cache is None:continue
        for point in cache.findall('c:pt',NS):
            index = int(point.get('idx'))
            value = point.findtext('c:v',default='',namespaces=NS)
            if value!='':cells[(int(start_row)+index//width,start+index%width)] = (value,reference.tag==q('c','numRef'))
    return sheets


def workbook_bytes(sheets):
    """Constrói XLSX mínimo válido com strings inline, números e estilos padrão.

    sheets é o mapa de cached_cells. Gera partes OPC usuais e não inclui tables
    artificiais, macros ou fórmulas externas. Os endereços mantêm os c:f originais.
    """
    book = ET.Element(f'{{{S}}}workbook');sheet_list = ET.SubElement(book,f'{{{S}}}sheets')
    rels = ET.Element(f'{{{R}}}Relationships');types = ET.Element(f'{{{CT}}}Types')
    ET.SubElement(types,f'{{{CT}}}Default',Extension='rels',ContentType='application/vnd.openxmlformats-package.relationships+xml')
    ET.SubElement(types,f'{{{CT}}}Default',Extension='xml',ContentType='application/xml')
    ET.SubElement(types,f'{{{CT}}}Override',PartName='/xl/workbook.xml',ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml')
    root_rels = ET.Element(f'{{{R}}}Relationships')
    ET.SubElement(root_rels,f'{{{R}}}Relationship',Id='rId1',Type=NS['r']+'/officeDocument',Target='xl/workbook.xml')
    files = {}
    for index,(name,cells) in enumerate((sheets or {'Sheet1':{}}).items(),1):
        ET.SubElement(sheet_list,f'{{{S}}}sheet',name=name,sheetId=str(index),attrib={q('r','id'):f'rId{index}'})
        ET.SubElement(rels,f'{{{R}}}Relationship',Id=f'rId{index}',Type=NS['r']+'/worksheet',Target=f'worksheets/sheet{index}.xml')
        part=f'xl/worksheets/sheet{index}.xml'
        ET.SubElement(types,f'{{{CT}}}Override',PartName='/'+part,ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml')
        sheet = ET.Element(f'{{{S}}}worksheet');data = ET.SubElement(sheet,f'{{{S}}}sheetData');row_nodes = {}
        for (row,column),(value,numeric) in sorted(cells.items()):
            if row not in row_nodes:row_nodes[row] = ET.SubElement(data,f'{{{S}}}row',r=str(row))
            cell = ET.SubElement(row_nodes[row],f'{{{S}}}c',r=f'{column_name(column)}{row}',t='n' if numeric else 'inlineStr')
            if numeric:ET.SubElement(cell,f'{{{S}}}v').text = value
            else:ET.SubElement(ET.SubElement(cell,f'{{{S}}}is'),f'{{{S}}}t').text = value
        files[part] = xml_bytes(sheet)
    files.update({'[Content_Types].xml':xml_bytes(types),'_rels/.rels':xml_bytes(root_rels),'xl/workbook.xml':xml_bytes(book),'xl/_rels/workbook.xml.rels':xml_bytes(rels)})
    output = io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,payload in files.items():archive.writestr(name,payload)
    return output.getvalue()


def normalize_chart_workbooks(parts):
    """Repara as planilhas dos gráficos ativos do pacote e retorna auditoria.

    XLSB recebe substituto XLSX construído dos caches do próprio gráfico. XLSX
    existente mantém todas as partes: remove apóstrofo final de table@ref e
    restaura números zero de caches onde 4.0.1 gravou um v vazio. Ranges inválidos
    restantes interrompem o build. O chamador aplica isto somente em quality.
    """
    repairs = []
    for part in list(parts):
        if not re.fullmatch(r'ppt/charts/(?:generated-)*chart\d+\.xml',part):continue
        chart = parse_xml(parts[part]);external = chart.find('c:externalData',NS)
        if external is None:continue
        relationship_part = rel_path(part)
        if relationship_part not in parts:continue
        relationships = parse_xml(parts[relationship_part])
        relationship = next((r for r in relationships if r.get('Id')==external.get(q('r','id'))),None)
        if relationship is None:raise ValueError(f'{part}: workbook sem relação')
        old = posixpath.normpath(posixpath.join(posixpath.dirname(part),relationship.get('Target')))
        if old.endswith('.xlsb'):
            target = f'ppt/embeddings/keynote-{posixpath.basename(part)[:-4]}.xlsx'
            parts[target] = workbook_bytes(cached_cells(chart))
            add_content_type(parts,target,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            relationship.set('Target',posixpath.relpath(target,posixpath.dirname(part)))
            parts[relationship_part] = xml_bytes(relationships)
            repairs.append({'chart':part,'workbook':target,'repair':'cached-xlsx-replaces-xlsb'})
        elif old.endswith('.xlsx'):
            source = zipfile.ZipFile(io.BytesIO(parts[old]));changed = {};ranges = 0
            for name in source.namelist():
                if name.startswith('xl/tables/') and name.endswith('.xml'):
                    root = parse_xml(source.read(name))
                    for node in root.iter():
                        if 'ref' not in node.attrib:continue
                        before = node.get('ref');after = before.rstrip("'")
                        if not re.fullmatch(r'\$?[A-Z]+\$?\d+(?::\$?[A-Z]+\$?\d+)?',after):raise ValueError(f'{old}: range inválido {before}')
                        if after!=before:node.set('ref',after);ranges+=1
                    if ranges:changed[name] = xml_bytes(root)
            zero_repairs = 0
            values = cached_cells(chart)
            workbook = parse_xml(source.read('xl/workbook.xml'))
            book_rels = parse_xml(source.read('xl/_rels/workbook.xml.rels'))
            targets = {r.get('Id'):r.get('Target') for r in book_rels}
            for sheet in workbook.findall(f'{{{S}}}sheets/{{{S}}}sheet'):
                target = targets[sheet.get(q('r','id'))]
                target = target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join('xl',target))
                root = parse_xml(source.read(target));updated = False
                cache = values.get(sheet.get('name'),{})
                for cell in root.findall(f'.//{{{S}}}c'):
                    value = cell.find(f'{{{S}}}v')
                    if value is None or value.text not in (None,'') or cell.get('t','n')!='n':continue
                    address = re.fullmatch(r'([A-Z]+)(\d+)',cell.get('r'))
                    datum = cache.get((int(address[2]),column_index(address[1])))
                    if datum and datum[1]:value.text=datum[0];zero_repairs+=1
                    else:cell.remove(value)
                    updated=True
                if updated:changed[target]=xml_bytes(root)
            if changed:
                output = io.BytesIO()
                with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
                    for item in source.infolist():archive.writestr(item,changed.get(item.filename,source.read(item.filename)))
                parts[old] = output.getvalue()
                repairs.append({'chart':part,'workbook':old,'repair':'valid-table-range','ranges':ranges,'zeroCells':zero_repairs})
    return repairs
