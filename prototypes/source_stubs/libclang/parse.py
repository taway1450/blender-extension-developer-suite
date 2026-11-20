"""Select the source files each area needs, parse them (2 worker processes) and cache the lowered result per unit.

The selection is a cheap text filter over the tree (a file defining an operator says ``wmOperatorType *ot``, a
Python type ``PyTypeObject``, ...); everything after it is read from clang's AST. A unit's cache key is its
arguments, the lowering version and the content of the files it holds.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from .flags import FlagSource, Unit

PATTERNS = {
    "rna": ("RNA_def_",),
    "operators": ("wmOperatorType *ot", "wmOperatorType *ot)", "WM_operatortype_append"),
    "python": ("PyTypeObject", "PyMethodDef", "PyModuleDef", "PyGetSetDef", "PyStructSequence"),
    "context": ("CTX_data_equals", "CTX_data_dir_set", "bContextDataResult *result"),
    "nodes": ("node_declare", "NodeDeclarationBuilder", "_node_type_base"),
}
TOPS = ("source/blender", "intern/audaspace", "extern/audaspace/bindings", "intern/cycles/blender")
# ``/source/blender/gpu/`` but not ``python/gpu/`` (the ``gpu`` module).
SKIP_PARTS = (
    "/tests/",
    "_test.cc",
    "_tests.cc",
    "/source/blender/draw/",
    "/source/blender/gpu/",
    "/compositor/",
    "/blenlib/",
    "/cycles/kernel/",
    "/io/usd/",
    "/io/alembic/",
    "/io/fbx/",
    "/makesdna/",
)


def select_files(source: Path) -> dict[str, list[Path]]:
    found: dict[str, set[Path]] = {area: set() for area in PATTERNS}
    for top in TOPS:
        base = source / top
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.suffix not in (".cc", ".c", ".cpp") or not path.is_file():
                continue
            rel = "/" + str(path.relative_to(source))
            if any(part in rel for part in SKIP_PARTS):
                continue
            if "/makesrna/intern/" in rel and (rel.endswith("_gen.cc") or "makesrna" in path.name):
                continue
            try:
                text = path.read_text(errors="replace")
            except OSError:
                continue
            for area, pats in PATTERNS.items():
                if any(p in text for p in pats):
                    found[area].add(path)
    found["bmesh"] = {source / "source/blender/bmesh/intern/bmesh_opdefines.cc"}
    return {area: sorted(files) for area, files in found.items()}


def _key(unit: Unit) -> str:
    h = hashlib.sha1()
    from .lower import LOWER_VERSION

    h.update(str(LOWER_VERSION).encode())
    h.update("\0".join(unit.args).encode())
    for f in [unit.path, *unit.files]:
        try:
            h.update(Path(f).read_bytes())
        except OSError:
            pass
    return h.hexdigest()[:20]


def _work(path: str, args: list[str], files: list[str], root: str, out: str) -> tuple[str, float, int]:
    from .lower import lower_tu

    start = time.perf_counter()
    try:
        data = lower_tu(path, args, files, root)
    except Exception as exc:  # keep going: a unit that fails is a warning
        data = {"tu": path, "files": files, "errors": -1, "first_errors": [repr(exc)], "functions": [], "globals": []}
    with gzip.open(out + ".tmp", "wt", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(out + ".tmp", out)
    return path, time.perf_counter() - start, data.get("errors", 0)


def parse_all(
    source: Path,
    flags: FlagSource,
    files: list[Path],
    cache: Path,
    jobs: int = 2,
    log=print,
    units_for=None,
) -> list[dict]:
    """Lower ``files`` (cached per unit and arguments); ``units_for`` picks each file's units (default:
    ``flags.units_for``; ``flags.runtime_unit`` for the runtime halves of the makesrna files)."""
    cache.mkdir(parents=True, exist_ok=True)
    units: dict[str, Unit] = {}
    wanted: dict[str, set[str]] = {}
    for f in files:
        for i, unit in enumerate((units_for or flags.units_for)(f)):
            ukey = unit.path if i == 0 else f"{unit.path}#{i}"
            units.setdefault(ukey, unit)
            wanted.setdefault(ukey, set()).add(str(f))
    todo = []
    results: dict[str, Path] = {}
    for path, unit in units.items():
        # A unity unit lowers only the files we selected from it.
        unit.files = [f for f in unit.files if f in wanted[path]] or unit.files
        key = _key(unit)
        out = cache / f"{Path(path).stem}-{key}.json.gz"
        results[path] = out
        if not out.exists():
            todo.append((unit, out))
    log(f"libclang: {len(units)} units ({len(todo)} to parse, {len(units) - len(todo)} cached), flags: {flags.kind}")
    if todo:
        start = time.perf_counter()
        done = 0
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            futures = [pool.submit(_work, u.path, u.args, u.files, str(source), str(out)) for u, out in todo]
            for fut in as_completed(futures):
                path, _seconds, _errors = fut.result()
                done += 1
                if done % 25 == 0 or done == len(todo):
                    log(f"  parsed {done}/{len(todo)} ({time.perf_counter() - start:.0f} s)")
                    sys.stdout.flush()
    lowered = []
    for path, out in results.items():
        with gzip.open(out, "rt", encoding="utf-8") as fh:
            lowered.append(json.load(fh))
    return lowered
