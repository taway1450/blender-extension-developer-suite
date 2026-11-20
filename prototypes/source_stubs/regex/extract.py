"""Runs the areas in order and records timings, warnings and what is out of reach."""

from __future__ import annotations

import json
import time
import traceback
from pathlib import Path
from typing import Any

from common.model import SourceModel
from ctok import Tree

UNREACHABLE = {
    "rna: DNA defaults": "struct property defaults come from DNA_*_defaults.h through makesrna's sdna lookup; not read",
    "rna: computed identifiers": "structs/properties whose identifier is computed at definition time (loops over "
    "socket types, string formatting) get no identifier; counted in warnings",
    "rna: Python-defined RNA": "bpy.props registrations come from the shared ast reader, not from C",
    "rna: values of C enums in item rows": "item values are evaluated from enums/#defines the file includes; "
    "expressions with casts of non-trivial types or sizeof stay unknown",
    "operators: runtime-only properties": "properties added in invoke/exec (RNA_def_* on a runtime srna) or by "
    "Python wrappers are not seen",
    "operators: conditional properties": "properties behind conditions on runtime state are kept (both branches run)",
    "pyapi: types built at runtime": "PyStructSequence types and types created with PyType_FromSpec or by copying "
    "are read from their field tables when static; bpy.types RNA classes are rendered from RNA instead",
    "context: computed members": "members whose name is not a string literal compared with CTX_data_equals or "
    "listed in a *_context_dir table are missed",
    "nodes: dynamic sockets": "sockets declared in loops/conditions over node storage are marked dynamic; "
    "sockets from socket item arrays (zones, bundles) are not enumerated",
}


def run_areas(tree: Tree, model: SourceModel, areas: list[str]) -> None:
    extra: dict[str, Any] = {}
    state: dict[str, Any] = {}
    for area in areas:
        start = time.perf_counter()
        try:
            if area == "rna":
                from rna_area import extract_rna

                builder, ip, enums = extract_rna(tree, model)
                state.update(builder=builder, ip=ip, enums=enums)
                _record(model, "rna", ip)
            elif area == "operators":
                from operators import extract_operators

                ip = extract_operators(tree, model, state)
                _record(model, "operators", ip)
            elif area == "nodes":
                from nodes import extract_nodes

                ip = extract_nodes(tree, model, state, extra)
                _record(model, "nodes", ip)
            elif area == "pyapi":
                from pyapi import extract_pyapi

                warnings = extract_pyapi(tree, model, extra)
                model.coverage.warnings += [f"pyapi: {w}" for w in warnings[:80]]
            elif area == "context":
                from context import extract_context

                extract_context(tree, model, state, extra)
            elif area == "bmesh":
                from bmesh_ops import extract_bmesh

                extract_bmesh(tree, model)
        except Exception:
            model.coverage.warnings.append(f"area {area} failed: {traceback.format_exc()}")
            traceback.print_exc()
        model.coverage.seconds[area] = time.perf_counter() - start
    if "builder" in state:
        state["builder"].finalize()
        enums = state["enums"]
        for name, arr in sorted(enums.shared.items()):
            if name.startswith("rna_enum_") or arr.items:
                model.enum_items[name] = arr.items
        model.coverage.warnings += enums.warnings[:100]
    model.coverage.warnings += sorted(set(tree.warnings))[:100]
    model.coverage.unreachable.update(UNREACHABLE)
    extra["preprocessor_warnings"] = len(set(tree.warnings))
    out = Path(__file__).resolve().parents[3] / ".cache" / "source-stubs"
    state["extra"] = extra
    model._extra = extra  # type: ignore[attr-defined]
    _write_extra(model, extra)


def _record(model: SourceModel, area: str, ip: Any) -> None:
    for kind, count in ip.warnings.most_common(60):
        model.coverage.warnings.append(f"{area}: {kind} (x{count})")


def _write_extra(model: SourceModel, extra: dict[str, Any]) -> None:
    import sys

    version = "5.2"
    for i, a in enumerate(sys.argv):
        if i == 1:
            version = a
    out = Path(__file__).resolve().parents[3] / ".cache" / "source-stubs" / version / "regex"
    out.mkdir(parents=True, exist_ok=True)
    (out / "extra.json").write_text(json.dumps(extra, indent=1, default=lambda v: sorted(v) if isinstance(v, set) else repr(v)), encoding="utf-8")
