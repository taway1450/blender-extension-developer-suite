"""Audit hand tables in the fork's stub generator against what a source reader found.

``ENUM_RUNTIME_ITEMS`` (``scripts/modules/_rna_info.py``) lists by hand the enums whose static items are not the ones
their callback gives at run time. A source reader knows every enum property that has both static items and an item
callback (``itemf``): each of them *may* give other items at run time. The audit lists the enums the table has, the
enums only the source facts flag, and the ones the table has but the facts do not support.

Usage:
  uv run --no-project --python 3.13 python prototypes/source_stubs/common/audit.py 5.2 [--tool makesrna]
Writes ``.cache/source-stubs/<version>/audit.md``.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.driver import REPO_ROOT, outputs_root
from common.model import SourceModel

PLACEHOLDERS = ({"DEFAULT"}, {"PLACEHOLDER"}, {"UNSUPPORTED"})


def table_from_source(path: Path, name: str) -> set[tuple[str, str]]:
    """The value of a module-level ``name = {(..., ...), ...}`` set literal."""
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return {tuple(item) for item in ast.literal_eval(node.value)}
    raise SystemExit(f"{name} not found in {path}")


def enums_with_callbacks(model: SourceModel) -> dict[tuple[str, str], tuple[str, list[str]]]:
    """``(struct, property) -> (itemf, static items)`` for every enum with real static items and an item callback."""
    found = {}
    for struct in model.structs:
        for prop in struct.properties:
            if prop.type != "enum" or not prop.itemf:
                continue
            items = [i.identifier for i in prop.items]
            if not items or set(items) in PLACEHOLDERS:
                continue
            found[(struct.identifier, prop.identifier)] = (prop.itemf, items)
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("version")
    parser.add_argument("--tool", default="makesrna")
    args = parser.parse_args()
    facts = outputs_root(args.version) / args.tool / "facts.json"
    if not facts.is_file():
        print(f"audit: {facts} not found, run the {args.tool} reader first")
        return 1
    model = SourceModel.read(facts)
    table = table_from_source(REPO_ROOT / "blender/scripts/modules/_rna_info.py", "ENUM_RUNTIME_ITEMS")
    found = enums_with_callbacks(model)
    lines = [
        f"# Hand-table audit: ENUM_RUNTIME_ITEMS vs {args.tool} (Blender {args.version})",
        "",
        f"The table lists {len(table)} enums; {len(found)} enum properties have static items and an item callback.",
        "",
        "## In the table and confirmed (static items + callback)",
        "",
    ]
    lines += [f"- `{s}.{p}`: `{found[(s, p)][0]}`" for s, p in sorted(table & found.keys())]
    lines += ["", "## In the table, but the source has no callback for it", ""]
    lines += [f"- `{s}.{p}`" for s, p in sorted(table - found.keys())] or ["- none"]
    lines += [
        "",
        "## Only in the source facts: static items + callback, not in the table",
        "",
        (
            "Candidates: the callback may give other items than the static ones (or only filter them, which the "
            "stubs can keep as a `Literal`). Each needs a look at the callback."
        ),
        "",
    ]
    for (s, p), (itemf, items) in sorted(found.items()):
        if (s, p) not in table:
            shown = ", ".join(items[:6]) + (", ..." if len(items) > 6 else "")
            lines.append(f"- `{s}.{p}`: `{itemf}` ({len(items)} static: {shown})")
    out = outputs_root(args.version) / "audit.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"Wrote {out}: {len(table & found.keys())} confirmed, {len(table - found.keys())} unsupported, "
        f"{len(found.keys() - table)} candidates"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
