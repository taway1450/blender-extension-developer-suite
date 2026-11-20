"""PROTOTYPE: RNA facts from Blender's own ``makesrna``, dumped as JSON.

``makesrna`` is the build step that runs every ``RNA_def_*`` call (``source/blender/makesrna/intern/rna_*.cc``) and
writes the C code of the RNA API. ``makesrna-json-dump.patch`` adds a JSON dump to it (``$RNA_JSON_DUMP``), written
after the definitions ran: every struct, property and function exactly as RNA defines them, plus what the runtime
no longer has, because makesrna still holds callbacks as the names of their functions (refine, enum item, pointer
type, editable, getter/setter) and knows each property's DNA field and each struct's source file.

It reads RNA only. Operators, the Python C API, context members, node declarations and bmesh operators are not
RNA definitions makesrna runs, so this prototype leaves them out (``coverage.md`` says so); the Python side
(``scripts/``) comes from the shared ``ast`` reader as for the other prototypes.

Prerequisites (once): apply the patch to the source tree and build the ``makesrna`` target:

    git -C .cache/blender-src/5.2-src apply prototypes/source_stubs/makesrna/makesrna-json-dump.patch
    mise run blender:build 5.2-src --ref v5.2.0 --config lite --target makesrna \\
        --define CMAKE_C_COMPILER=/usr/bin/clang --define CMAKE_CXX_COMPILER=/usr/bin/clang++ ...

Then:

    uv run --no-project --python 3.13 python prototypes/source_stubs/makesrna/run.py 5.2 --source .cache/blender-src/5.2-src
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.driver import CACHE_DIR, main, out_dir
from common.model import EnumItem, RnaFunction, RnaProperty, RnaStruct, SourceModel

PATCH = Path(__file__).resolve().parent / "makesrna-json-dump.patch"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--build",
        type=Path,
        help="CMake build directory with bin/makesrna (default: .cache/blender-build/<source name>)",
    )
    parser.add_argument("--json", type=Path, help="Read this dump instead of running makesrna")


def name_of(flag: str, prefix: str) -> str:
    return flag.removeprefix(prefix).lower()


def items_of(raw: list[dict]) -> list[EnumItem]:
    return [
        EnumItem(
            identifier=i["identifier"],
            name=i.get("name") or "",
            description=i.get("description") or "",
            value=i.get("value"),
        )
        for i in raw
        if i.get("identifier")
    ]


def convert_property(raw: dict, src: str) -> RnaProperty:
    flags = raw.get("flag", [])
    p = RnaProperty(identifier=raw["identifier"], type=raw["type"], src=src)
    p.subtype = name_of(raw.get("subtype") or "PROP_NONE", "PROP_")
    p.unit = name_of(raw.get("unit") or "PROP_UNIT_NONE", "PROP_UNIT_")
    p.name = raw.get("name") or ""
    p.description = raw.get("description") or ""
    p.array = [n for n in raw.get("array", []) if n]
    p.dynamic_array = bool(raw.get("getlength")) or "PROP_DYNAMIC" in flags
    p.flags = [name_of(f, "PROP_") for f in flags]
    p.parameter_flags = [name_of(f, "PARM_") for f in raw.get("flag_parameter", [])]
    p.editable_func = raw.get("editable") or ""
    p.readonly = "PROP_EDITABLE" not in flags and not p.editable_func
    p.never_null = "PROP_NEVER_NULL" in flags
    p.getter = raw.get("get") or raw.get("get_array") or ""
    p.setter = raw.get("set") or raw.get("set_array") or ""
    p.deprecated = "deprecated" in raw
    if raw.get("dna_name"):
        p.dna = f"{raw.get('dna_struct') or ''}.{raw['dna_name']}"
    for key in ("hard_min", "hard_max", "soft_min", "soft_max"):
        value = raw.get(key)
        if isinstance(value, (int, float)):
            setattr(p, key, value)
    if raw["type"] == "string":
        p.max_length = raw.get("max_length") or None
        p.default = raw.get("default") or ""
    elif raw["type"] == "enum":
        p.items = items_of(raw.get("items", []))
        p.items_name = raw.get("items_name") or ""
        p.itemf = raw.get("itemf") or ""
        p.enum_flag = "PROP_ENUM_FLAG" in flags
        default = raw.get("default", 0)
        if p.enum_flag:
            p.default = sorted(i.identifier for i in p.items if i.value and default & i.value == i.value)
        else:
            p.default = next((i.identifier for i in p.items if i.value == default), None)
    elif raw["type"] in {"pointer", "collection"}:
        p.struct_type = raw.get("struct_type") or ""
        p.typef = raw.get("typef") or ""
        p.poll = raw.get("poll") or ""
        p.collection_srna = raw.get("srna") or ""
    else:
        p.default = raw.get("default")
    return p


def convert(dump: dict, model: SourceModel) -> None:
    for raw in dump["structs"]:
        src = f"source/blender/makesrna/intern/{raw['filename']}" if raw.get("filename") else "makesrna"
        s = RnaStruct(
            identifier=raw["identifier"],
            base=raw.get("base") or "",
            name=raw.get("name") or "",
            description=raw.get("description") or "",
            nested=raw.get("nested") or "",
            name_property=raw.get("name_property") or "",
            refine=raw.get("refine") or "",
            path_func=raw.get("path") or "",
            register=raw.get("register") or "",
            idprops=bool(raw.get("idproperties")),
            flags=[name_of(f, "STRUCT_") for f in raw.get("flag", [])],
            dna=raw.get("dna") or "",
            src=src,
        )
        s.properties = [convert_property(p, src) for p in raw.get("properties", [])]
        for rf in raw.get("functions", []):
            f = RnaFunction(
                identifier=rf["identifier"],
                description=rf.get("description") or "",
                flags=[name_of(x, "FUNC_") for x in rf.get("flag", [])],
                c_function=rf.get("call") or "",
                returns=rf.get("return") or "",
                src=src,
            )
            f.parameters = [convert_property(p, src) for p in rf.get("parameters", [])]
            s.functions.append(f)
        model.structs.append(s)
    for name, raw in dump.get("enums", {}).items():
        model.enum_items[name] = items_of(raw.get("items", []))


def run_makesrna(source: Path, build: Path, work: Path) -> Path:
    binary = build / "bin" / "makesrna"
    makesrna_cc = source / "source/blender/makesrna/intern/makesrna.cc"
    if "RNA_JSON_DUMP" not in makesrna_cc.read_text(encoding="utf-8"):
        raise SystemExit(f"{makesrna_cc} lacks the JSON dump: git -C {source} apply {PATCH}, then rebuild makesrna")
    if not binary.is_file():
        raise SystemExit(f"{binary} not found: build the makesrna target first (see this script's docstring)")
    if binary.stat().st_mtime < makesrna_cc.stat().st_mtime:
        raise SystemExit(f"{binary} is older than {makesrna_cc}: rebuild the makesrna target")
    out = work / "rna.json"
    gen = work / "gen" / "intern"
    gen.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, RNA_JSON_DUMP=str(out))
    libs = CACHE_DIR / "blender-libs" / "linux_x64"
    if libs.is_dir():
        env["LD_LIBRARY_PATH"] = os.pathsep.join(str(p) for p in sorted(libs.glob("*/lib")))
    proc = subprocess.run(
        [str(binary), f"{source}/source/blender/makesdna/", f"{gen}/", f"{gen.parent}/"],
        env=env,
        capture_output=True,
        text=True,
        cwd=work,
    )
    (work / "makesrna.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    if proc.returncode or not out.is_file():
        raise SystemExit(f"makesrna failed ({proc.returncode}), see {work / 'makesrna.log'}")
    return out


def extract(source: Path, model: SourceModel, args: argparse.Namespace) -> None:
    work = out_dir(args.version, "makesrna") / "work"
    work.mkdir(parents=True, exist_ok=True)
    path = args.json or run_makesrna(source, args.build or CACHE_DIR / "blender-build" / source.name, work)
    convert(json.loads(path.read_text(encoding="utf-8")), model)
    model.coverage.unreachable.update(
        {
            "operators": "Operators are registered at runtime (wmOperatorType), not defined by makesrna.",
            "python_c_api": "mathutils, gpu, bmesh, bpy.props, ... are C extension types, not RNA.",
            "context": "bpy.context members come from the editors' context callbacks, not RNA.",
            "nodes": "Node structs registered at runtime (most built-in nodes in 5.x) and their socket declarations "
            "are not makesrna definitions; only the node structs rna_nodetree.cc defines are here.",
            "bmesh_ops": "bmesh operators are a C table (bmesh_opdefines.cc), not RNA.",
            "source_lines": "makesrna knows each struct's source file but no line numbers.",
            "build": "Needs a configured Blender build (CMake, precompiled libraries) and the makesrna target built.",
        }
    )


if __name__ == "__main__":
    sys.exit(main("makesrna", extract, __doc__, add_arguments))
