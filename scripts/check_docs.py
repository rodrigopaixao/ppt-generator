"""Verifica documentação inline de funções nomeadas e métodos do projeto.

Callbacks anônimos pequenos são explicados pela função que os contém. Funções
nomeadas Python exigem docstring; funções/métodos/helpers nomeados JavaScript
exigem JSDoc. Isto verifica presença, não certifica a qualidade editorial.
"""
import ast
import json
import re
from pathlib import Path


def previous_jsdoc(source, start):
    """Confere se a declaração é precedida imediatamente por comentário JSDoc."""
    prefix = source[:start].rstrip()
    if not prefix.endswith('*/'):
        return False
    opening = prefix.rfind('/**')
    return opening >= 0 and prefix.find('*/', opening) == len(prefix)-2


def check(root):
    """Retorna declarações documentadas e ausentes em src/ e scripts/.

    O scanner JS reconhece declarations, métodos e helpers arrow nomeados;
    o Python usa AST real, incluindo funções internas como scene_nodes.visit.
    """
    missing, documented = [], []
    patterns = [r'^(?:export )?(?:async )?function\s+(\w+)\s*\(',
                r'^  (constructor|\w+)\([^;\n]*\)\s*\{',
                r'^\s*const\s+(\w+)\s*=\s*(?:\([^;\n]*\)|\w+)\s*=>']
    controls = {'if', 'for', 'while', 'switch', 'catch'}
    for filename in sorted((root/'src').glob('*.mjs')):
        source = filename.read_text()
        for pattern in patterns:
            for match in re.finditer(pattern, source, re.M):
                name = match.group(1)
                if name in controls:
                    continue
                entry = {'file': str(filename.relative_to(root)), 'function': name,
                         'line': source.count('\n', 0, match.start())+1}
                (documented if previous_jsdoc(source, match.start()) else missing).append(entry)
    for filename in sorted((root/'scripts').glob('*.py')):
        tree = ast.parse(filename.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                entry = {'file': str(filename.relative_to(root)), 'function': node.name, 'line': node.lineno}
                (documented if ast.get_docstring(node) else missing).append(entry)
    return {'documented': len(documented), 'missing': missing, 'functions': documented}


def main():
    """Imprime o relatório; termina com erro se houver declaração sem documentação."""
    root = Path(__file__).resolve().parent.parent
    report = check(root)
    (root/'output/documentation-report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({'documented': report['documented'], 'missing': report['missing']}, indent=2))
    if report['missing']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
