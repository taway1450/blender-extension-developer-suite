"""Compile flags for the libclang reader (``libclang/flags.py``)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from libclang.flags import FlagSource


def tree(tmp_path: Path) -> tuple[Path, FlagSource]:
    src, build = tmp_path / "src", tmp_path / "build"
    intern = src / "source/blender/makesrna/intern"
    intern.mkdir(parents=True, exist_ok=True)
    (intern / "rna_object.cc").write_text('#include "rna_internal.hh"\nStructRNA *x = RNA_Object;\n')
    (intern / "rna_object_api.cc").write_text("RNA_ObjectBase;\n")
    deg = src / "source/blender/depsgraph"
    (deg / "intern").mkdir(parents=True, exist_ok=True)
    (deg / "DEG_depsgraph_query.hh").write_text("#pragma once\n")
    (deg / "intern/depsgraph_query.cc").write_text("")
    gen = build / "source/blender/makesrna/intern"
    entries = [
        {"file": str(intern / "rna_object.cc"), "command": f"clang++ -DMAKESRNA -c {intern / 'rna_object.cc'}"},
        {
            "file": str(gen / "rna_object_gen.cc"),
            "command": f"clang++ -DRNA_RUNTIME -I/profile -c {gen / 'rna_object_gen.cc'}",
        },
        {
            "file": str(deg / "intern/depsgraph_query.cc"),
            "command": f"clang++ -DDEG -c {deg / 'intern/depsgraph_query.cc'}",
        },
    ]
    build.mkdir(exist_ok=True)
    (build / "compile_commands.json").write_text(json.dumps(entries))
    return src, FlagSource(src, build / "compile_commands.json", tmp_path / "shim")


def test_runtime_units_use_the_generated_units_flags(tmp_path: Path) -> None:
    """``rna_*.cc`` and ``rna_*_api.cc`` are compiled at runtime through ``rna_*_gen.cc`` (bf_rna), which defines
    ``RNA_RUNTIME``, has the full include paths and includes ``RNA_prototypes.hh`` first."""
    src, flags = tree(tmp_path)
    for name in ("rna_object.cc", "rna_object_api.cc"):
        unit = flags.runtime_unit(src / "source/blender/makesrna/intern" / name)
        assert unit.path.endswith(name)
        assert "-DRNA_RUNTIME" in unit.args and "-I/profile" in unit.args and "-DMAKESRNA" not in unit.args
        i = unit.args.index("-include")
        assert unit.args[i + 1] == "RNA_prototypes.hh"


def test_units_never_stop_at_the_error_limit(tmp_path: Path) -> None:
    """Clang's default limit of 20 errors is fatal: the rest of the unit would not be parsed."""
    src, flags = tree(tmp_path)
    assert "-ferror-limit=0" in flags.unit_for(src / "source/blender/makesrna/intern/rna_object.cc").args


def test_the_shim_declares_every_rna_struct_the_makesrna_files_name(tmp_path: Path) -> None:
    _src, _flags = tree(tmp_path)
    shim = (tmp_path / "shim" / "RNA_prototypes.hh").read_text()
    assert "RNA_Object;" in shim and "RNA_ObjectBase;" in shim


def test_headers_borrow_the_flags_of_a_unit_below_them(tmp_path: Path) -> None:
    src, flags = tree(tmp_path)
    assert "-DDEG" in flags.unit_for(src / "source/blender/depsgraph/DEG_depsgraph_query.hh").args


def generated(tmp_path: Path) -> tuple[Path, FlagSource]:
    """A build whose codegen ran: the real ``RNA_prototypes.hh`` and ``rna_object_gen.cc`` exist."""
    src, _ = tree(tmp_path)
    build = tmp_path / "build"
    gen = build / "source/blender/makesrna/intern"
    gen.mkdir(parents=True, exist_ok=True)
    (gen / "rna_object_gen.cc").write_text(
        '#include "RNA_prototypes.hh"\n#include "rna_object.cc"\n#include "rna_object_api.cc"\n'
    )
    (build / "source/blender/makesrna/RNA_prototypes.hh").write_text("#pragma once\n")
    (build / "source/blender/makesdna/intern").mkdir(parents=True, exist_ok=True)
    (build / "source/blender/makesdna/intern/dna_type_offsets.h").write_text("#pragma once\n")
    return src, FlagSource(src, build / "compile_commands.json", tmp_path / "shim")


def test_runtime_halves_are_parsed_as_the_generated_unit_that_includes_both(tmp_path: Path) -> None:
    """With the codegen done, ``rna_X.cc`` and ``rna_X_api.cc`` are parsed once, as ``rna_X_gen.cc``: the unit
    Blender compiles, where the first file's declarations are visible to the second."""
    src, flags = generated(tmp_path)
    intern = src / "source/blender/makesrna/intern"
    a, b = flags.runtime_unit(intern / "rna_object.cc"), flags.runtime_unit(intern / "rna_object_api.cc")
    assert a.path == b.path and a.path.endswith("rna_object_gen.cc")
    assert a.files == [str(intern / "rna_object.cc"), str(intern / "rna_object_api.cc")]
    assert "-DRNA_RUNTIME" in a.args and "-include" not in a.args


def test_real_generated_headers_replace_the_shim(tmp_path: Path) -> None:
    """A shim written before the codegen ran must not shadow the real headers."""
    tree(tmp_path)  # writes the shim: no generated headers yet
    assert (tmp_path / "shim" / "RNA_prototypes.hh").exists()
    _src, flags = generated(tmp_path)
    assert not (tmp_path / "shim" / "RNA_prototypes.hh").exists()
    assert not (tmp_path / "shim" / "dna_type_offsets.h").exists()
    assert flags.missing_generated == []
