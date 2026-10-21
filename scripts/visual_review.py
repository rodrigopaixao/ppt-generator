"""Compare all slides pixel by pixel using the same LibreOffice and fonts.

Images are private QA evidence rather than final slide content. Expose hidden
slide 68 in temporary copies of both files. Ignore PDF metadata and compare only
the rendered pixels on each page."""
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
    """Create a review copy exposing hidden slides without changing the input file.

    Replace show=0 with show=1 lexically without reserializing DrawingML.
    source/destination are Paths. Return the created copy's path."""
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as target:
        for name in original.namelist():
            payload = original.read(name)
            if name.startswith('ppt/slides/slide') and name.endswith('.xml'):
                payload = payload.replace(b' show="0"', b' show="1"')
            target.writestr(name, payload)
    return destination


def command(arguments):
    """Run a binary without a shell and surface its stderr on failure.

    arguments contains individual command-line items. A ten-minute timeout limits
    stalled conversions; the caller can monitor the process."""
    subprocess.run([str(value) for value in arguments], check=True, timeout=600)


def compare(reference, output, directory, scale=960):
    """Render reference/output and compute exact pixel equality per page.

    Args: reference/output are PPTX files; directory receives PDFs, PNGs and reports;
    scale is maximum width in pixels. Pillow reads/compares images and builds contact
    sheets, but never draws presentation content. Return matches, mean errors and
    input hashes."""
    from PIL import Image, ImageChops, ImageStat, ImageDraw
    directory.mkdir(parents=True, exist_ok=True)
    ref = visible_copy(reference, directory/'reference-visible.pptx')
    candidate = visible_copy(output, directory/'candidate-visible.pptx')
    print('Rendering 71 slides from the reference and output...', flush=True)
    command(['soffice', '--headless', '--convert-to', 'pdf', '--outdir', directory, ref, candidate])
    for name in ('reference', 'candidate'):
        print('Rasterizing '+name+'...', flush=True)
        command(['pdftoppm', '-scale-to', str(scale), '-png', directory/f'{name}-visible.pdf', directory/name])
    reference_pages = sorted(directory.glob('reference-*.png'))
    candidate_pages = sorted(directory.glob('candidate-*.png'))
    if len(reference_pages) != len(candidate_pages) or not reference_pages:
        raise ValueError('Rendered page counts differ')
    pages = []
    for index, (a, b) in enumerate(zip(reference_pages, candidate_pages), 1):
        left, right = Image.open(a).convert('RGB'), Image.open(b).convert('RGB')
        if left.size != right.size:
            raise ValueError(f'Page {index} has different dimensions')
        delta = ImageChops.difference(left, right)
        pages.append({'slide': index, 'pixelIdentical': delta.getbbox() is None,
                      'meanAbsoluteError': sum(ImageStat.Stat(delta).mean)/3})
    # All 71 pages fit on six contact sheets; the last sheet may contain fewer pages.
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
    """CLI: configure output/reference paths and keep review evidence in a dedicated folder."""
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, default=root/'2606 Context Enriched Slide Repository.pptx')
    parser.add_argument('--output', type=Path, default=root/'output/recreated-slides.pptx')
    parser.add_argument('--directory', type=Path, default=root/'output/review/full')
    parser.add_argument('--scale', type=int, default=960)
    args = parser.parse_args()
    result = compare(args.reference, args.output, args.directory, args.scale)
    if result['exactPixelMatches'] != result['pages']:
        sys.exit('Review found visual differences; see visual-report.json')


if __name__ == '__main__':
    main()
