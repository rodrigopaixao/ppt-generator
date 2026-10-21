"""Render reviewed output and create private contact sheets for human inspection.

PNGs/PDFs are QA evidence and never replace PowerPoint objects. Record hashes,
page counts, page mapping and the rendering engine in the report."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw


def run(arguments):
    """Run an argument list without a shell; fail immediately if review commands fail."""
    subprocess.run([str(value) for value in arguments], check=True, timeout=600)


def review(source, directory):
    """Export a PPTX, render pages and compose 3×4 contact sheets in reading order.

    source is an existing PPTX; directory receives private evidence. The build
    manifest supplies original slide numbers, including continuations. The final
    hash confirms that rendering did not modify the reviewed package."""
    source, directory = source.resolve(), directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = json.loads(source.with_suffix('.layout.json').read_text())
    run(['soffice','--headless','--convert-to','pdf','--outdir',directory,source])
    pdf = directory/(source.stem+'.pdf')
    run(['pdftoppm','-scale-to','1100','-png',pdf,directory/'page'])
    images = sorted(directory.glob('page-*.png'))
    if len(images) != manifest['counts']['outputSlides']:
        raise ValueError('Rendered page count does not match the manifest')
    for start in range(0,len(images),12):
        contact = Image.new('RGB',(1500,1240),'#e8e8e8')
        draw = ImageDraw.Draw(contact)
        for offset, filename in enumerate(images[start:start+12]):
            picture = Image.open(filename).convert('RGB')
            picture.thumbnail((490,280))
            x,y = offset%3*500,offset//3*310
            entry = manifest['slides'][start+offset]
            label = f"Page {start+offset+1} | Source {entry['sourceNumber']}"
            if entry.get('page'):
                label += f" (continued {entry['page']})"
            draw.text((x+5,y+5),label,fill='black')
            contact.paste(picture,(x+5,y+25))
        contact.save(directory/f'contact-{start//12+1}.jpg',quality=92)
    assert digest == hashlib.sha256(source.read_bytes()).hexdigest()
    result = {'outputSha256':digest,'pages':len(images),'renderer':'LibreOffice',
      'estimatedOverflow':len(manifest['quality']['estimatedOverflow']),
      'contacts':len(list(directory.glob('contact-*.jpg')))}
    (directory/'review-report.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)


def main():
    """Read CLI input/output paths and start reviewing the actual output."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path('output/recreated-slides.pptx'))
    parser.add_argument('--directory',type=Path,default=Path('output/review/quality-final'))
    args = parser.parse_args()
    review(args.source,args.directory)


if __name__ == '__main__':
    main()
