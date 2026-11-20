"""Compare stub sets: the three source readers with Blender's builtin stubs, fake-bpy-module and each other.

For every pair it counts modules, classes and members each has alone, and, for members both have, whether the
annotations agree after normalising spelling (module qualifiers, ``Optional``, union order). Disagreements are
sorted into kinds (``Literal`` vs ``str``, ``X | None`` vs ``X``, ``bpy_prop_array`` vs a mathutils class, ...),
so the numbers say *how* two generators differ, not only how often.

Usage:
  uv run --no-project --python 3.13 python prototypes/source_stubs/common/compare.py 5.2
Writes ``.cache/source-stubs/<version>/comparison.md`` and ``comparison.json``.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import warnings
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore", category=SyntaxWarning)  # escape sequences in parsed docstrings

from common.driver import CACHE_DIR, TOOLS, outputs_root

AREAS = (
    ("bpy.types", lambda m: m == "bpy.types"),
    ("bpy.ops", lambda m: m.startswith("bpy.ops")),
    ("bpy (other)", lambda m: m.startswith("bpy") and not m.startswith(("bpy.types", "bpy.ops", "bpy_extras"))),
    ("mathutils", lambda m: m.startswith("mathutils")),
    ("gpu", lambda m: m.startswith("gpu")),
    ("bmesh", lambda m: m.startswith("bmesh")),
    ("freestyle", lambda m: m.startswith("freestyle")),
    ("other C modules", lambda m: m.split(".")[0] in {"blf", "imbuf", "idprop", "bl_math", "aud", "bgl"}),
    ("bpy_extras", lambda m: m.startswith("bpy_extras")),
    ("Python scripts", lambda m: True),
)


def area_of(module: str) -> str:
    for name, test in AREAS:
        if test(module):
            return name
    return "Python scripts"


def module_name(root: Path, path: Path) -> str:
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    if parts:
        parts[0] = parts[0].removesuffix("-stubs")
    return ".".join(parts)


def annotation(node: ast.AST) -> str:
    if isinstance(node, ast.AnnAssign):
        return ast.unparse(node.annotation)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        decorators = {ast.unparse(d) for d in node.decorator_list}
        if decorators & {"property", "builtins.property"}:
            return ast.unparse(node.returns) if node.returns else "?"
        args = node.args
        names = [a.arg for a in [*args.posonlyargs, *args.args] if a.arg not in {"self", "cls"}]
        pos_only = [a.arg for a in args.posonlyargs if a.arg not in {"self", "cls"}]
        kwonly = [a.arg for a in args.kwonlyargs]
        sig = ", ".join(
            f"{a.arg}: {ast.unparse(a.annotation) if a.annotation else '?'}"
            for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]
            if a.arg not in {"self", "cls"}
        )
        flags = ("/" if pos_only and len(pos_only) == len(names) else "") + ("*" if kwonly else "")
        return f"({sig}){flags} -> {ast.unparse(node.returns) if node.returns else '?'}"
    if isinstance(node, ast.Assign):
        return "= " + ast.unparse(node.value)[:60]
    return "?"


def operator_class_call(node: ast.ClassDef) -> ast.FunctionDef | None:
    """The ``__new__`` of a fake-bpy-module operator class (``class add(bpy.ops._BPyOpsSubModOp)``)."""
    if not any(ast.unparse(base).endswith("_BPyOpsSubModOp") for base in node.bases):
        return None
    return next((i for i in node.body if isinstance(i, ast.FunctionDef) and i.name == "__new__"), None)


def read_stubs(root: Path) -> dict[str, dict[str, dict[str, str]]]:
    """``module -> class -> member -> annotation`` (module level under class ``""``)."""
    modules: dict[str, dict[str, dict[str, str]]] = {}
    for path in sorted(root.rglob("*.py*")):
        if path.suffix not in {".pyi", ".py"} or "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        classes: dict[str, dict[str, str]] = {"": {}}
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and (call := operator_class_call(node)):
                # fake-bpy-module writes each operator as a class whose ``__new__`` is the call.
                classes[""].setdefault(node.name, annotation(call))
            elif isinstance(node, ast.ClassDef):
                members = classes.setdefault(node.name, {})
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        members.setdefault(item.target.id, annotation(item))
                    elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name in members and "@overload" not in members[item.name]:
                            continue
                        members[item.name] = annotation(item)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                classes[""].setdefault(node.target.id, annotation(node))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                classes[""].setdefault(node.name, annotation(node))
        modules.setdefault(module_name(root, path), {}).update(classes)
    return modules


def type_aliases(root: Path) -> dict[str, str]:
    """Module-level ``X: TypeAlias = ...`` / ``X = Literal[...]`` of a stub set (builtin's ``_rna_enums``)."""
    aliases: dict[str, str] = {}
    for path in root.rglob("*.pyi"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in tree.body:
            if isinstance(node, ast.TypeAlias):  # ``type X = Literal[...]`` (fake-bpy-module)
                aliases[node.name.id] = ast.unparse(node.value)
            elif isinstance(node, ast.AnnAssign) and node.value and ast.unparse(node.annotation).endswith("TypeAlias"):
                aliases[ast.unparse(node.target)] = ast.unparse(node.value)
            elif (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and ast.unparse(node.value).startswith(("Literal[", "typing.Literal["))
            ):
                aliases[node.targets[0].id] = ast.unparse(node.value)
    return aliases


def expand_aliases(modules: dict[str, dict[str, dict[str, str]]], aliases: dict[str, str]) -> None:
    """Spell each alias out in every annotation, so ``rna_enum_x_items`` and its ``Literal[...]`` compare equal."""
    if not aliases:
        return
    pattern = re.compile(
        r"\b(?:[\w.]+\.)?(" + "|".join(map(re.escape, sorted(aliases, key=len, reverse=True))) + r")\b"
    )
    for classes in modules.values():
        for members in classes.values():
            for name, text in members.items():
                text = pattern.sub(lambda m: aliases[m.group(1)], text)
                # ``Literal[Alias]`` with the alias itself a ``Literal[...]`` (fake-bpy-module)
                members[name] = re.sub(r"(?:typing\.)?Literal\[\s*((?:typing\.)?Literal\[[^\[\]]*\])\s*\]", r"\1", text)


_QUALIFIER = re.compile(
    r"\b(?:bpy\.types|mathutils|bmesh\.types|gpu\.types|freestyle\.types|typing|collections\.abc|builtins|_rna_enums)\."
)


def normalize(text: str) -> str:
    t = _QUALIFIER.sub("", text).replace(" ", "")
    t = re.sub(r"Optional\[([^\[\]]+)\]", r"\1|None", t)

    # Sort the members of top-level unions.
    def sort_union(s: str) -> str:
        depth, parts, cur = 0, [], ""
        for ch in s:
            if ch in "[(":
                depth += 1
            elif ch in "])":
                depth -= 1
            if ch == "|" and depth == 0:
                parts.append(cur)
                cur = ""
            else:
                cur += ch
        parts.append(cur)
        return "|".join(sorted(set(parts))) if len(parts) > 1 else s

    if "->" in t:
        head, _, ret = t.rpartition("->")
        return f"{head}->{sort_union(ret)}"
    return sort_union(t)


_OPERATOR_PREFIX = re.compile(r"^\(execution_context:[^,)]*(,undo:[^,)]*)?,?")


def operator_call(sig: str) -> str:
    """An operator's signature without the positional ``execution_context`` / ``undo`` every operator takes: a
    convention some stub sets spell out and others leave out, not a fact about the operator."""
    if not _OPERATOR_PREFIX.match(sig):
        return sig
    head, _, ret = sig.rpartition("->")
    head = _OPERATOR_PREFIX.sub("(", head)
    params, _, flags = head.rpartition(")")
    flags = flags.replace("/", "")
    return f"{params}){flags}->{ret}"


def difference_kind(a: str, b: str) -> str:
    if a == "?" or b == "?":
        return "one side untyped"
    if "->" in a and "->" not in b or "->" in b and "->" not in a:
        return "method vs attribute"
    if "->" in a:
        ha, ra = a.rsplit("->", 1)
        hb, rb = b.rsplit("->", 1)
        if ha == hb:
            return "return type: " + difference_kind(ra, rb)
        if ha.replace("/", "").replace("*", "") == hb.replace("/", "").replace("*", ""):
            return "parameter kinds (positional-only / keyword-only)"
        names_a = re.findall(r"(\w+):", ha)
        names_b = re.findall(r"(\w+):", hb)
        if names_a != names_b:
            return "parameter names or count"
        if re.sub(r"\|None(?=[,)])|None\|", "", ha) == re.sub(r"\|None(?=[,)])|None\|", "", hb):
            return "parameter nullability"
        if (":?" in ha) != (":?" in hb):
            return "one side untyped"
        return "parameter types"
    if set(a.split("|")) - {"None"} == set(b.split("|")) - {"None"}:
        return "nullability (X | None vs X)"
    if ("Literal[" in a) != ("Literal[" in b) and ("str" in (a, b) or "set[str]" in (a, b)):
        return "Literal vs str (dynamic enum)"
    if "Literal[" in a and "Literal[" in b:
        return "different Literal items"
    if "bpy_prop_array" in a or "bpy_prop_array" in b:
        return "bpy_prop_array vs another type"
    if "Any" in (a, b):
        return "Any vs a type"
    if "bpy_prop_collection" in a or "bpy_prop_collection" in b:
        return "collection spelling"
    if "rna_enum" in a or "rna_enum" in b:
        return "enum alias vs inline"
    return "other"


def compare_pair(a: dict, b: dict) -> dict:
    stats: dict = {"areas": defaultdict(Counter), "kinds": Counter(), "samples": defaultdict(list)}
    for module in sorted(set(a) | set(b)):
        area = area_of(module)
        counter = stats["areas"][area]
        if module not in b:
            counter["modules only A"] += 1
            counter["members only A"] += sum(len(m) for m in a[module].values())
            continue
        if module not in a:
            counter["modules only B"] += 1
            counter["members only B"] += sum(len(m) for m in b[module].values())
            continue
        counter["modules both"] += 1
        for cls in sorted(set(a[module]) | set(b[module])):
            ma, mb = a[module].get(cls), b[module].get(cls)
            if ma is None:
                counter["classes only B"] += 1
                counter["members only B"] += len(mb)
                if len(stats["samples"]["class only B"]) < 15:
                    stats["samples"]["class only B"].append(f"{module}.{cls}")
                continue
            if mb is None:
                counter["classes only A"] += 1
                counter["members only A"] += len(ma)
                if len(stats["samples"]["class only A"]) < 15:
                    stats["samples"]["class only A"].append(f"{module}.{cls}")
                continue
            if cls:
                counter["classes both"] += 1
            for member in sorted(set(ma) | set(mb)):
                if member not in mb:
                    counter["members only A"] += 1
                    if len(stats["samples"]["member only A"]) < 15:
                        stats["samples"]["member only A"].append(f"{module}.{cls}.{member}".replace("..", "."))
                elif member not in ma:
                    counter["members only B"] += 1
                    if len(stats["samples"]["member only B"]) < 15:
                        stats["samples"]["member only B"].append(f"{module}.{cls}.{member}".replace("..", "."))
                else:
                    na, nb = normalize(ma[member]), normalize(mb[member])
                    if module.startswith("bpy.ops."):
                        na, nb = operator_call(na), operator_call(nb)
                    if na == nb:
                        counter["members same"] += 1
                    else:
                        counter["members differ"] += 1
                        kind = difference_kind(na, nb)
                        stats["kinds"][kind] += 1
                        if len(stats["samples"][kind]) < 6:
                            stats["samples"][kind].append(
                                f"{module}.{cls}.{member}: {ma[member][:110]}  ||  {mb[member][:110]}".replace(
                                    "..", "."
                                )
                            )
    return stats


def stub_sets(version: str) -> dict[str, Path]:
    sets = {
        "builtin": CACHE_DIR / "bpy-stubs-builtin" / version,
        "fake-bpy": CACHE_DIR / "bpy-stubs" / version,
    }
    for tool in TOOLS:
        sets[tool] = outputs_root(version) / tool / "stubs"
    return {name: path for name, path in sets.items() if path.is_dir()}


def totals(counter: Counter) -> Counter:
    return counter


def markdown(version: str, sets: dict[str, Path], data: dict, pairs: dict) -> str:
    lines = [f"# Source stub readers vs the other generators (Blender {version})", ""]
    lines += [
        "Stub sets: "
        + ", ".join(
            f"`{n}` ({sum(sum(len(m) for m in c.values()) for c in data[n].values())} members in {len(data[n])} modules)"
            for n in sets
        ),
        "",
    ]
    lines += [
        "Members are attributes, properties and methods; a class's members are compared only when both sets have the class.",
        "",
    ]
    for (a, b), stats in pairs.items():
        lines += [f"## {a} (A) vs {b} (B)", ""]
        lines += [
            "| Area | modules A/both/B | classes A/both/B | members only A | members only B | same | differ | agree % |",
            "|---|---|---|---|---|---|---|---|",
        ]
        total = Counter()
        for area, _ in AREAS:
            c = stats["areas"].get(area)
            if not c:
                continue
            total.update(c)
            both = c["members same"] + c["members differ"]
            agree = f"{100 * c['members same'] / both:.0f}" if both else "-"
            lines.append(
                f"| {area} | {c['modules only A']}/{c['modules both']}/{c['modules only B']} | {c['classes only A']}/{c['classes both']}/{c['classes only B']} | {c['members only A']} | {c['members only B']} | {c['members same']} | {c['members differ']} | {agree} |"
            )
        both = total["members same"] + total["members differ"]
        lines.append(
            f"| **all** | {total['modules only A']}/{total['modules both']}/{total['modules only B']} | {total['classes only A']}/{total['classes both']}/{total['classes only B']} | {total['members only A']} | {total['members only B']} | {total['members same']} | {total['members differ']} | {100 * total['members same'] / both:.0f} |"
            if both
            else "| **all** | | | | | | | |"
        )
        lines.append("")
        if stats["kinds"]:
            lines += ["Kinds of disagreement:", ""]
            for kind, n in stats["kinds"].most_common():
                lines.append(f"- {kind}: {n}")
                for sample in stats["samples"].get(kind, [])[:3]:
                    lines.append(f"  - `{sample}`")
            lines.append("")
        for key in ("class only A", "class only B", "member only A", "member only B"):
            if stats["samples"].get(key):
                lines.append(f"- Samples, {key}: " + ", ".join(f"`{s}`" for s in stats["samples"][key][:10]))
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("version")
    parser.add_argument(
        "--pairs", default="", help="Comma-separated A:B pairs (default: every prototype against every set)"
    )
    args = parser.parse_args()
    sets = stub_sets(args.version)
    data = {name: read_stubs(path) for name, path in sets.items()}
    for name, path in sets.items():
        expand_aliases(data[name], type_aliases(path))
    prototypes = [n for n in sets if n in TOOLS]
    if args.pairs:
        wanted = [tuple(p.split(":")) for p in args.pairs.split(",")]
    else:
        wanted = [(p, ref) for p in prototypes for ref in ("builtin", "fake-bpy") if ref in sets]
        wanted += list(combinations(prototypes, 2))
        if "builtin" in sets and "fake-bpy" in sets:
            wanted.append(("builtin", "fake-bpy"))
    pairs = {(a, b): compare_pair(data[a], data[b]) for a, b in wanted}
    out = outputs_root(args.version)
    out.mkdir(parents=True, exist_ok=True)
    (out / "comparison.md").write_text(markdown(args.version, sets, data, pairs), encoding="utf-8")
    (out / "comparison.json").write_text(
        json.dumps(
            {
                f"{a}|{b}": {"areas": {k: dict(v) for k, v in s["areas"].items()}, "kinds": dict(s["kinds"])}
                for (a, b), s in pairs.items()
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {out / 'comparison.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
