"""Compara todos os slides por pixels usando o mesmo LibreOffice e as mesmas fontes.

Não converte o produto final em imagens. As imagens são evidência privada de QA.
O slide oculto 68 é exposto em cópias temporárias de AMBOS os arquivos para ser
comparado. Metadados do PDF são ignorados; somente pixels de cada página contam.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


def visible_copy(source, destination):
    """Cria cópia de revisão expondo slides ocultos, sem tocar no arquivo de entrada.

    A alteração é lexical (show="0" -> show="1") e não reserializa DrawingML.
    source/destination são Paths. Retorna o caminho da cópia criada.
    """
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as target:
        for name in original.namelist():
            payload = original.read(name)
            if name.startswith('ppt/slides/slide') and name.endswith('.xml'):
                payload = payload.replace(b' show="0"', b' show="1"')
            target.writestr(name, payload)
    return destination


def command(arguments):
    """Executa um binário sem shell e falha com stderr completo se houver erro.

    argumentos contém cada item da linha de comando separado. O timeout limita
    uma conversão travada a dez minutos; o chamador pode acompanhar o processo.
    """
    subprocess.run([str(value) for value in arguments], check=True, timeout=600)


def compare(reference, output, directory, scale=960):
    """Renderiza referência e resultado e calcula igualdade exata por página.

    Args: reference/output são PPTX; directory recebe PDFs/PNGs/relatório;
    scale é a largura máxima, em pixels. Usa Pillow apenas para ler/comparar e
    montar contatos, nunca para desenhar conteúdo da apresentação.
    Returns: relatório com matches, erros médios e hashes das entradas.
    """
    from PIL import Image, ImageChops, ImageStat, ImageDraw
    directory.mkdir(parents=True, exist_ok=True)
    ref = visible_copy(reference, directory/'reference-visible.pptx')
    candidate = visible_copy(output, directory/'candidate-visible.pptx')
    print('Renderizando 71 slides da referência e da saída...', flush=True)
    command(['soffice', '--headless', '--convert-to', 'pdf', '--outdir', directory, ref, candidate])
    for name in ('reference', 'candidate'):
        print('Rasterizando '+name+'...', flush=True)
        command(['pdftoppm', '-scale-to', str(scale), '-png', directory/f'{name}-visible.pdf', directory/name])
    reference_pages = sorted(directory.glob('reference-*.png'))
    candidate_pages = sorted(directory.glob('candidate-*.png'))
    if len(reference_pages) != len(candidate_pages) or not reference_pages:
        raise ValueError('Número de páginas renderizadas diverge')
    pages = []
    for index, (a, b) in enumerate(zip(reference_pages, candidate_pages), 1):
        left, right = Image.open(a).convert('RGB'), Image.open(b).convert('RGB')
        if left.size != right.size:
            raise ValueError(f'Página {index} com dimensões diferentes')
        delta = ImageChops.difference(left, right)
        pages.append({'slide': index, 'pixelIdentical': delta.getbbox() is None,
                      'meanAbsoluteError': sum(ImageStat.Stat(delta).mean)/3})
    # Todas as 71 páginas cabem em seis contatos; o último contato pode ter menos páginas.
    for start in range(0, len(candidate_pages), 12):
        width, height = Image.open(candidate_pages[start]).size
        sheet = Image.new('RGB', (width*3, (height+25)*4), '#dddddd')
        draw = ImageDraw.Draw(sheet)
        for offset, filename in enumerate(candidate_pages[start:start+12]):
            x, y = (offset % 3)*width, (offset//3)*(height+25)
            sheet.paste(Image.open(filename).convert('RGB'), (x, y+25))
            draw.text((x+8, y+7), f'Slide {start+offset+1}', fill='black')
        sheet.save(directory/f'contact-{start//12+1}.jpg', quality=88)
    report = {'renderer': 'LibreOffice + Poppler, same environment for both decks',
        'fontScope': 'Compares available system fonts; does not certify missing Scotia font files.',
        'referenceSha256': hashlib.sha256(reference.read_bytes()).hexdigest(),
        'outputSha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'resolution': scale, 'pages': len(pages),
        'exactPixelMatches': sum(page['pixelIdentical'] for page in pages), 'results': pages}
    (directory/'visual-report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({key: report[key] for key in ('pages', 'exactPixelMatches', 'resolution')}), flush=True)
    return report


def main():
    """CLI: permite trocar a saída/referência e mantém a revisão em pasta dedicada."""
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, default=root/'2606 Context Enriched Slide Repository.pptx')
    parser.add_argument('--output', type=Path, default=root/'output/recreated-slides.pptx')
    parser.add_argument('--directory', type=Path, default=root/'output/review/full')
    parser.add_argument('--scale', type=int, default=960)
    args = parser.parse_args()
    result = compare(args.reference, args.output, args.directory, args.scale)
    if result['exactPixelMatches'] != result['pages']:
        sys.exit('A revisão encontrou diferenças visuais; veja visual-report.json')


if __name__ == '__main__':
    main()
