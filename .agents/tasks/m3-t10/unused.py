import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

for name in sys.argv[1:]:
    tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) or isinstance(node, ast.Import):
            for alias in node.names:
                imported[(alias.asname or alias.name).split(".")[0]] = node.lineno
    used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    used |= {node.value.id for node in ast.walk(tree) if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)}
    print(name, sorted(key for key in imported if key not in used))
