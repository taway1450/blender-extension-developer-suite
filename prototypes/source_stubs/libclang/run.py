"""libclang source reader: Blender's C/C++ read through clang's AST (macros expanded, calls resolved, types known).

Each selected file is parsed with libclang (flags from CMake's compile_commands.json, or synthesized) and lowered to
a small JSON AST, cached per translation unit; an abstract interpreter then runs the definition code the way
Blender runs it at build/registration time (RNA_def_* bodies, operator type functions, module init functions,
context callbacks, node registration and declarations) and records what it defines.

    uv run --no-project --python 3.13 --with libclang==18.1.1 python prototypes/source_stubs/libclang/run.py 5.2 \\
        --source .cache/blender-src/5.2-src
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from _resources import default_jobs

from common.driver import build_dir, main, out_dir
from common.model import SourceModel
from libclang import crosscheck
from libclang.bmesh import read_bmesh
from libclang.context import Context
from libclang.flags import FlagSource
from libclang.interp import Interp, Obj, Program
from libclang.nodes import Nodes
from libclang.operators import Operators
from libclang.parse import parse_all, select_files
from libclang.pyapi import PyApi
from libclang.returns import callee_files, classify, definition_index, report
from libclang.rna import Rna


def add_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--compile-commands",
        type=Path,
        help="compile_commands.json (default: .cache/blender-build/<source dir name>/compile_commands.json)",
    )
    group.add_argument("--synthesize-flags", action="store_true", help="Ignore any compile_commands.json")
    parser.add_argument("--jobs", type=int, help="Parser processes (default and maximum: the suite's job limit)")


def extract(source: Path, model: SourceModel, args: argparse.Namespace) -> None:
    version = args.version
    out = out_dir(version, "libclang")
    timings = model.coverage.seconds
    cc = None
    if not args.synthesize_flags:
        cc = args.compile_commands or build_dir(source) / "compile_commands.json"
        if not cc.exists():
            cc = None
    flags = FlagSource(source, cc, out / ("shim" if cc else "shim-synth"))
    start = time.perf_counter()
    selection = select_files(source)
    files = sorted({f for fs in selection.values() for f in fs})
    cache = out / ("cache" if cc else "cache-synth")
    lowered = parse_all(source, flags, files, cache, jobs=max(1, min(args.jobs or default_jobs(), default_jobs())))
    timings["parse (libclang, cached per unit)"] = time.perf_counter() - start

    start = time.perf_counter()
    program = Program(lowered)
    interp = Interp(program)
    rna = Rna(interp, model)
    ops = Operators(interp, rna, model)
    pyapi = PyApi(interp, model)
    ctx = Context(interp, rna, model)
    nodes = Nodes(interp, rna, model)
    timings["index"] = time.perf_counter() - start

    rel = {area: {str(f.relative_to(source)) for f in fs} for area, fs in selection.items()}
    # 1. RNA: each makesrna file's RNA_def_<x>(BlenderRNA *brna) entry, with brna bound.
    start = time.perf_counter()
    brna = Obj("brna")
    entries = [
        f
        for f in program.functions.values()
        if f.file.startswith("source/blender/makesrna/intern/rna_")
        and f.name.startswith("RNA_def_")
        and not f.file.endswith("rna_define.cc")
        and len(f.params) == 1
        and "BlenderRNA" in f.params[0][1]
    ]
    for fn in sorted(entries, key=lambda f: (f.file, f.line)):
        interp.call_function(fn, [brna])
    timings["rna"] = time.perf_counter() - start
    # 2. Nodes (registration defines node structs and their RNA)
    start = time.perf_counter()
    nodes.run(rel["nodes"])
    timings["nodes"] = time.perf_counter() - start
    # 3. Operators
    start = time.perf_counter()
    ops.run()
    timings["operators"] = time.perf_counter() - start
    # 4. Python C API
    start = time.perf_counter()
    pyapi.run()
    timings["python C API"] = time.perf_counter() - start
    # 5. Context
    start = time.perf_counter()
    ctx.run(rel["context"])
    timings["context"] = time.perf_counter() - start
    # 6. bmesh
    read_bmesh(interp, source, model)
    rna.finish()
    # 7. RNA function returns: the runtime bodies, then their callees, a few rounds deep
    start = time.perf_counter()
    jobs = max(1, min(args.jobs or default_jobs(), default_jobs()))
    runtime = sorted((source / "source/blender/makesrna/intern").glob("rna_*.cc"))
    extra = parse_all(source, flags, runtime, cache, jobs=jobs, units_for=lambda f: [flags.runtime_unit(f)])
    index = definition_index(source)
    parsed = {str(f.relative_to(source)) for f in files}
    for _round in range(4):
        _counts, returns = classify(model, Program(extra + lowered))
        todo = sorted(callee_files(returns.unresolved, index) - parsed)
        if not todo:
            break
        parsed.update(todo)
        extra += parse_all(source, flags, [source / f for f in todo], cache, jobs=jobs)
    final = Program(extra + lowered)
    classify(model, final)
    out.mkdir(parents=True, exist_ok=True)
    (out / "returns.md").write_text(report(model), encoding="utf-8")
    timings["returns"] = time.perf_counter() - start
    # 8. Cross-check the return verdicts with LLVM and the Clang Static Analyzer (needs the generated units)
    start = time.perf_counter()
    checks: dict[str, int] = {}
    units = crosscheck.plan(model, final, cc, source) if cc else []
    if units:
        results = crosscheck.run(units, out / "crosscheck-cache", jobs)
        text, checks = crosscheck.report(model, final, results)
        (out / "crosscheck.md").write_text(text, encoding="utf-8")
    else:
        print("crosscheck: skipped (no generated rna_*_gen.cc units: run blender:build --target codegen)")
    timings["crosscheck"] = time.perf_counter() - start

    # Coverage notes
    cov = model.coverage
    cov.unreachable.update(
        {
            "flags": f"{flags.kind}; generated headers replaced by declaration shims: {', '.join(flags.missing_generated) or 'none'}",
            "rna DNA defaults": "makesrna takes many property defaults from DNA_*_defaults.h through SDNA at build time; "
            "only defaults given in RNA_def_* calls are read",
            "rna runtime-registered structs": "structs registered from Python (bpy.types.Panel subclasses, add-ons) and "
            "RNA built from data at runtime (ID properties, geometry attributes)",
            "dynamic enums": "items of enums with an item function (itemf) exist only at runtime: the function is named",
            "loops": "a definition inside a loop runs once with an unknown index (identifiers built with sprintf "
            "are lost); unknown conditions run both branches",
            "context": "members answered by Python (bl_ui, add-ons) or by generic fall-backs (CTX_data_* from bContext "
            "fields in BKE_context) are not callbacks of an editor",
            "comments": "comments are not in clang's AST: bmesh docs are read from the text at AST positions",
        }
    )
    errors = {tu: n for tu, n in program.errors.items() if n}
    cov.warnings.append(
        f"{len(errors)} of {len(program.errors)} translation units had clang errors "
        f"({sum(n for n in errors.values() if n > 0)} errors); parsing continued"
    )
    for tu, n in sorted(errors.items(), key=lambda kv: -kv[1])[:15]:
        cov.warnings.append(f"clang errors: {tu}: {n}")
    for name, n in Counter(interp.unresolved).most_common(25):
        cov.warnings.append(f"unresolved call (no body in the parsed files): {name} x{n}")
    cov.warnings.extend(interp.warnings[:50])
    cov.warnings.append(f"RNA properties defined with an unknown identifier or container: {rna.dynamic_props}")
    cov.warnings.append(f"interpreter: {interp.calls_followed} calls followed into function bodies")
    extra = {
        "flags": flags.kind,
        "units": len(program.errors),
        "units_with_errors": len(errors),
        "returns_crosscheck": checks,
        "nodes_registered": nodes.registered,
        "rna_struct_dna": dict(sorted(rna.dna_of.items())),
        "python_struct_sequences": sorted(pyapi.structseq),
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "extra.json").write_text(json.dumps(extra, indent=1))


if __name__ == "__main__":
    sys.exit(main("libclang", extract, __doc__, add_arguments))
