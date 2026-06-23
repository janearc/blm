#!/usr/bin/env python3
# bounce docstrings. the house standard (engineering_standards.md §4) bans
# docstrings for internal logic -- intent belongs in lowercase # comments, which
# sit next to the line they explain and rot loudly, not in a "..." block that goes
# stale and unread above a signature. ruff has no rule for this, so we walk the ast:
# any module / class / function whose FIRST statement is a bare string literal is a
# docstring and fails. non-first string literals (legit multi-line data) are ignored,
# so this never false-positives the way a `"""` grep would.
#
# this is the fleet-canonical copy. it is vendored (copied) into each repo's
# tools/lint/, not shared as a dependency -- per the v0.5 fan-out decision.
import ast
import sys
from pathlib import Path


def _docstring_lines(path):
    # yield the line number of every docstring node in one file.
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    nodes = [tree]
    nodes += [
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    for node in nodes:
        if ast.get_docstring(node, clean=False) is not None:
            yield node.body[0].lineno


def main(argv):
    # check every path given (a file, or a dir walked for *.py; default cwd). skip
    # directories that are never ours to check -- virtualenvs, caches, vendored trees,
    # build output -- so pointing the checker at a package dir can't trip over its .venv.
    skip = {".venv", "venv", "__pycache__", ".git", "node_modules", "dist", "build", ".tox", ".mypy_cache"}
    files = []
    for arg in argv or ["."]:
        p = Path(arg)
        if p.is_file():
            files.append(p)
        else:
            files += [f for f in sorted(p.rglob("*.py")) if not (skip & set(f.parts))]
    hits = []
    for f in files:
        for line in _docstring_lines(f):
            hits.append(f"{f}:{line}: docstring banned -- use # comments (standards §4)")
    if hits:
        print("\n".join(hits), file=sys.stderr)
        print(f"\n{len(hits)} docstring(s) found; the house standard bans them.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
