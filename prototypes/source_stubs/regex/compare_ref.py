"""Measure the regex stubs against the builtin reference stubs: classes, members and member types that agree.

Usage: python compare_ref.py [version] [module ...]   (default: 5.2 bpy.types mathutils bpy.ops.object)
Prints per-module totals and the first differences. A measurement aid, not part of the generator.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / ".cache"


def norm(t: str) -> str:
    t = re.sub(r"\b(?:bpy\.types|mathutils|bmesh\.types|bpy)\.", "", t)
    t = t.replace(" ", "")
    return t


def members(path: Path) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """class -> member -> type text; module-level functions -> signature text."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    classes: dict[str, dict[str, str]] = {}
    funcs: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            body: dict[str, str] = {}
            for m in node.body:
                if isinstance(m, ast.AnnAssign) and isinstance(m.target, ast.Name):
                    body[m.target.id] = ast.unparse(m.annotation)
                elif isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    decos = {ast.unparse(d) for d in m.decorator_list}
                    if "property" in decos:
                        body[m.name] = ast.unparse(m.returns) if m.returns else ""
                    elif any(d.endswith(".setter") for d in decos) or m.name in body:
                        continue
                    else:
                        body[m.name] = (
                            "def(" + ast.unparse(m.args) + ")->" + (ast.unparse(m.returns) if m.returns else "")
                        )
            classes[node.name] = body
        elif isinstance(node, ast.FunctionDef):
            funcs[node.name] = "(" + ast.unparse(node.args) + ")"
    return classes, funcs


def compare(version: str, module: str, show: int = 12) -> None:
    rel = Path(*module.split(".")) / "__init__.pyi"
    ref_path = ROOT / "bpy-stubs-builtin" / version / rel
    our_path = ROOT / "source-stubs" / version / "regex" / "stubs" / rel
    if not ref_path.exists() or not our_path.exists():
        print(f"{module}: missing {'reference' if not ref_path.exists() else 'ours'}")
        return
    ref_c, ref_f = members(ref_path)
    our_c, our_f = members(our_path)
    cls_hit = [c for c in ref_c if c in our_c]
    mem_total = mem_hit = type_hit = 0
    missing: list[str] = []
    wrong: list[str] = []
    for c in cls_hit:
        for m, t in ref_c[c].items():
            if m.startswith("bl_rna") or m in {"rna_type"}:
                continue
            mem_total += 1
            if m in our_c[c]:
                mem_hit += 1
                if norm(our_c[c][m]) == norm(t):
                    type_hit += 1
                elif len(wrong) < 400:
                    wrong.append(f"{c}.{m}: ours {our_c[c][m]} | ref {t}")
            elif len(missing) < 400:
                missing.append(f"{c}.{m}")
    extra_cls = [c for c in our_c if c not in ref_c and not c.startswith("_")]
    f_hit = [f for f in ref_f if f in our_f]
    print(
        f"== {module}: classes {len(cls_hit)}/{len(ref_c)} (+{len(extra_cls)} not in ref), "
        f"members {mem_hit}/{mem_total} ({100 * mem_hit / max(mem_total, 1):.1f}%), "
        f"same type {type_hit}/{mem_hit} ({100 * type_hit / max(mem_hit, 1):.1f}%), functions {len(f_hit)}/{len(ref_f)}"
    )
    if show:
        print("  missing classes:", [c for c in ref_c if c not in our_c][:show])
        print("  missing members:", missing[:show])
        for w in wrong[:show]:
            print("  differs:", w)
        sig_diff = [f for f in f_hit if norm(our_f[f]) != norm(ref_f[f])]
        for f in sig_diff[: show // 2]:
            print(f"  signature {f}: ours {our_f[f]} | ref {ref_f[f]}")


if __name__ == "__main__":
    args = sys.argv[1:]
    version = args.pop(0) if args and re.match(r"^\d", args[0]) else "5.2"
    for mod in args or ["bpy.types", "mathutils", "bpy.ops.object"]:
        compare(version, mod)
