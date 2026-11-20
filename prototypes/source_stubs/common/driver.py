"""The command line every prototype shares: read a Blender source tree, write facts, stubs and coverage.

A prototype's ``run.py`` calls ``main(tool, extract)`` with its extraction function ``extract(source, model)``,
which fills the C/C++ part of ``model`` (RNA, operators, the Python C API, context, nodes, bmesh). The Python part
(``scripts/`` read with ``ast``) is shared and added here, so the prototypes differ only in how they read C/C++.

Outputs, under ``.cache/source-stubs/<version>/<tool>/``:

- ``facts.json``: the ``SourceModel``;
- ``stubs/``: the rendered ``.pyi`` (``common/render.py``);
- ``coverage.md``: counts per area, what the tool could not reach, timings.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from .model import SourceModel
from .pysource import read_python
from .render import write_stubs

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from _resources import guarded
from build_blender import BUILD_DIR, LIBS_DIR, lib_platform

CACHE_DIR = REPO_ROOT / ".cache"
# The source readers, in the order they run and are compared.
TOOLS = ("regex", "libclang", "makesrna")


def source_tree(version: str) -> Path:
    """The source worktree ``stubs:generate`` / ``blender:build`` made for ``version``."""
    return CACHE_DIR / "blender-src" / version


def outputs_root(version: str) -> Path:
    """``.cache/source-stubs/<version>``: every reader's outputs, the comparison and the audit."""
    path = CACHE_DIR / "source-stubs" / version
    path.mkdir(parents=True, exist_ok=True)
    return path


def out_dir(version: str, tool: str) -> Path:
    path = outputs_root(version) / tool
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_dir(source: Path) -> Path:
    """The CMake build ``blender:build`` made for a source worktree (``makesrna``, ``compile_commands.json``)."""
    return BUILD_DIR / source.name


def precompiled_libraries() -> Path:
    """Blender's precompiled libraries for this machine (``.cache/blender-libs/<platform>``)."""
    return LIBS_DIR / lib_platform()


def count(model: SourceModel) -> dict[str, int]:
    returns = Counter(f.returns_null for s in model.structs for f in s.functions if f.returns_null)
    return {
        **{f"rna_pointer_returns_{kind}": n for kind, n in sorted(returns.items())},
        "rna_structs": len(model.structs),
        "rna_properties": sum(len(s.properties) for s in model.structs),
        "rna_functions": sum(len(s.functions) for s in model.structs),
        "rna_dynamic_enums": sum(1 for s in model.structs for p in s.properties if p.type == "enum" and p.itemf),
        "rna_refine_funcs": sum(1 for s in model.structs if s.refine),
        "rna_typef_pointers": sum(1 for s in model.structs for p in s.properties if p.typef),
        "rna_never_null": sum(1 for s in model.structs for p in s.properties if p.never_null),
        "shared_enum_arrays": len(model.enum_items),
        "operators": len(model.operators),
        "operator_properties": sum(len(o.properties) for o in model.operators),
        "py_types": len(model.py_types),
        "py_type_methods": sum(len(t.methods) for t in model.py_types),
        "py_type_getsets": sum(len(t.getsets) for t in model.py_types),
        "py_type_slots": sum(len(t.slots) for t in model.py_types),
        "py_modules": len(model.py_modules),
        "py_module_functions": sum(len(m.methods) for m in model.py_modules),
        "py_signatures_from_docstrings": sum(1 for t in model.py_types for m in t.methods if m.signature)
        + sum(1 for mod in model.py_modules for m in mod.methods if m.signature),
        "context_members": len(model.context),
        "node_decls": len(model.nodes),
        "node_sockets": sum(len(n.inputs) + len(n.outputs) for n in model.nodes),
        "bmesh_ops": len(model.bmesh_ops),
        "python_modules": len(model.python),
        "python_classes": sum(len(m.classes) for m in model.python),
        "python_registrations": len(model.registrations),
    }


def coverage_markdown(model: SourceModel, stub_files: int) -> str:
    lines = [f"# Coverage: {model.tool}", "", f"Source: `{model.source}` at `{model.commit[:12]}`", ""]
    lines += ["| Area | Count |", "|---|---|"]
    for key, value in model.coverage.counts.items():
        lines.append(f"| {key} | {value} |")
    lines += [f"| stub files | {stub_files} |", ""]
    if model.coverage.unreachable:
        lines += ["## Not reachable with this tool", ""]
        lines += [f"- **{area}**: {why}" for area, why in model.coverage.unreachable.items()]
        lines.append("")
    if model.coverage.seconds:
        lines += ["## Time", ""] + [f"- {k}: {v:.1f} s" for k, v in model.coverage.seconds.items()] + [""]
    if model.coverage.warnings:
        lines += ["## Warnings", ""] + [f"- {w}" for w in model.coverage.warnings[:200]]
        if len(model.coverage.warnings) > 200:
            lines.append(f"- ... {len(model.coverage.warnings) - 200} more")
    return "\n".join(lines) + "\n"


def main(
    tool: str,
    extract: Callable[[Path, SourceModel, argparse.Namespace], None],
    doc: str | None = None,
    add_arguments: Callable[[argparse.ArgumentParser], None] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("version", help="Source worktree name under .cache/blender-src (e.g. 5.2)")
    parser.add_argument("--source", type=Path, help="Blender source tree (default: .cache/blender-src/<version>)")
    parser.add_argument("--no-python", action="store_true", help="Skip the shared ast reader of scripts/")
    if add_arguments:
        add_arguments(parser)
    args = parser.parse_args()
    source = (args.source or source_tree(args.version)).resolve()
    if not (source / "source" / "blender").is_dir():
        print(f"error: {source} is not a Blender source tree", file=sys.stderr)
        return 1
    commit = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    model = SourceModel(tool=tool, source=str(source), commit=commit)
    out = out_dir(args.version, tool)

    with guarded():  # the suite's machine-wide lock and resource limits (scripts/_resources.py)
        start = time.perf_counter()
        extract(source, model, args)
        model.coverage.seconds["extract"] = time.perf_counter() - start
    if not args.no_python:
        start = time.perf_counter()
        read_python(source, model)
        model.coverage.seconds["python (ast)"] = time.perf_counter() - start
    model.coverage.counts = count(model)
    model.write(out / "facts.json")
    start = time.perf_counter()
    files = write_stubs(model, out / "stubs")
    model.coverage.seconds["render"] = time.perf_counter() - start
    (out / "coverage.md").write_text(coverage_markdown(model, len(files)), encoding="utf-8")
    print(f"{tool}: {len(files)} stub files, facts and coverage in {out}")
    for key, value in model.coverage.counts.items():
        print(f"  {key}: {value}")
    return 0
