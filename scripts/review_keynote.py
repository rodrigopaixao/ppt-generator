"""Valida o PPTX no Keynote usando uma cópia temporária e exportação PDF privada."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def review(source, directory):
    """Abre somente cópia privada; conta slides/charts e exporta o PDF do Keynote.

    source é o PPTX final com manifesto .layout.json. directory recebe PDF e
    auditoria de hash. Nunca salva ou fecha documentos previamente abertos pelo
    usuário. Erros de importação ou contagem interrompem a validação.
    """
    source=source.resolve();directory=directory.resolve();directory.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(source.with_suffix('.layout.json').read_text())
    expected_charts=sum(e['kind']=='chart' for s in manifest['slides'] for e in s['elements'])
    digest=hashlib.sha256(source.read_bytes()).hexdigest();pdf=directory/'validated.pdf'
    with tempfile.TemporaryDirectory(prefix='keynote-review-') as staging:
        copy=Path(staging)/'review-copy.pptx';shutil.copyfile(source,copy)
        script=Path(staging)/'review.applescript'
        script.write_text(f'''with timeout of 240 seconds
 tell application "Keynote"
  set reviewDeck to open POSIX file {json.dumps(str(copy))}
  try
   set chartCount to 0
   repeat with s in slides of reviewDeck
    set chartCount to chartCount + (count of charts of s)
   end repeat
   set slideCount to count of slides of reviewDeck
   set appVersion to version
   export reviewDeck to POSIX file {json.dumps(str(pdf))} as PDF
   close reviewDeck saving no
   return (slideCount as text) & "," & (chartCount as text) & "," & appVersion
  on error messageText number errorCode
   close reviewDeck saving no
   error messageText number errorCode
  end try
 end tell
end timeout
''')
        result=subprocess.run(['osascript',str(script)],capture_output=True,text=True,check=True,timeout=270)
    slides,charts,version=result.stdout.strip().split(',')
    if int(slides)!=manifest['counts']['outputSlides'] or int(charts)!=expected_charts:
        raise ValueError(f'Keynote: slides={slides}, charts={charts}; esperado {manifest["counts"]["outputSlides"]}, {expected_charts}')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=digest:raise ValueError('Fonte mudou durante a revisão')
    audit={'outputSha256':digest,'renderer':'Keynote','version':version,'slides':int(slides),'nativeCharts':int(charts),'pdf':str(pdf)}
    (directory/'review-report.json').write_text(json.dumps(audit,indent=2))
    print(json.dumps(audit))


def main():
    """Recebe a saída final e o diretório privado de revisão pela linha de comando."""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path('output/recreated-slides.pptx'))
    parser.add_argument('--directory',type=Path,default=Path('output/review/keynote'))
    args=parser.parse_args();review(args.source,args.directory)


if __name__=='__main__':main()
