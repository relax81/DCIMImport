"""Jeder tr()-Text muss eine englische Übersetzung mit denselben Platzhaltern haben."""
import ast
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dcim_import.i18n import EN  # noqa: E402

PKG = Path(__file__).resolve().parents[1] / "dcim_import"


def texts():
    for f in PKG.glob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant) \
                    and isinstance(node.args[0].value, str):
                name = getattr(node.func, "id", getattr(node.func, "attr", ""))
                if name == "tr" or (name == "cb" and len(node.args) == 3):
                    yield f.name, node.args[0].value
            # msg = ("…" if … else "…")  -> tr(msg, …)
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.IfExp):
                for c in (node.value.body, node.value.orelse):
                    if isinstance(c, ast.Constant) and isinstance(c.value, str) and "{n}" in c.value:
                        yield f.name, c.value


def fields(s):
    return {f for _, f, _, _ in string.Formatter().parse(s) if f}


def test_all_translated():
    missing = [(f, t) for f, t in texts() if t not in EN]
    assert not missing, missing


def test_placeholders_match():
    bad = [k for k, v in EN.items() if fields(k) != fields(v)]
    assert not bad, bad
