"""Compile flags per source file: from CMake's ``compile_commands.json`` or synthesized from the tree.

``compile_commands.json`` gives the exact flags of the build (defines, include paths, the bundled libraries'
headers). Unity builds (``Unity/unity_N_cxx.cxx``) list their sources as ``#include "/abs/x.cc"``: such a source is
parsed through its unity file, and the lowering keeps the definitions of each included file apart.

Without a build, flags are synthesized: ``-x c++ -std=c++20``, ``-I`` for every directory holding headers under
``source/blender``, ``intern`` and ``extern`` and a few feature defines. Generated headers come from the build
(``blender:build --target codegen``); while it has not made them (``RNA_prototypes.hh``, ``dna_type_offsets.h``)
a shim directory stands in (only declarations; no facts are read from it): an undeclared ``RNA_Object`` would
otherwise make clang drop the whole call that names it.
"""

from __future__ import annotations

import json
import re
import shlex
import sysconfig
from dataclasses import dataclass, field
from pathlib import Path

from common.driver import precompiled_libraries

RESOURCE_INCLUDE = "/usr/lib/llvm-18/lib/clang/18/include"
SYNTH_DEFINES = [
    "WITH_PYTHON",
    "WITH_FREESTYLE",
    "WITH_INTERNATIONAL",
    "WITH_AUDASPACE",
    "WITH_INPUT_NDOF",
    "WITH_FLUID",
    "WITH_IO_WAVEFRONT_OBJ",
    "WITH_IO_PLY",
    "WITH_IO_STL",
    "WITH_TBB",
    "__LITTLE_ENDIAN__",
    "WITH_OPENGL_BACKEND",
]


@dataclass
class Unit:
    """One translation unit to parse: its path, arguments and the source files whose definitions it holds."""

    path: str
    args: list[str]
    files: list[str] = field(default_factory=list)


def _clean(command: str | list[str], file: str) -> list[str]:
    parts = shlex.split(command) if isinstance(command, str) else list(command)
    out: list[str] = []
    skip = False
    # Precompiled headers the build may not have produced: keep ``-include cmake_pch.hxx``, drop ``-include-pch``.
    cleaned: list[str] = []
    i = 1
    while i < len(parts):
        if parts[i] == "-Xclang" and i + 3 < len(parts) and parts[i + 1] == "-include-pch":
            i += 4
            continue
        if parts[i] == "-Xclang" and i + 3 < len(parts) and parts[i + 1] == "-include" and parts[i + 2] == "-Xclang":
            cleaned += ["-include", parts[i + 3]]
            i += 4
            continue
        cleaned.append(parts[i])
        i += 1
    parts = [parts[0], *cleaned]
    for a in parts[1:]:
        if skip:
            skip = False
            continue
        if a in ("-o", "-c", "-MF", "-MT", "-MQ"):
            skip = True
            continue
        if a == file or a.startswith(("-W", "-O", "-march", "-f", "-g")) or a in ("-pipe", "-MD", "-MMD"):
            continue
        out.append(a)
    return out


class FlagSource:
    def __init__(self, source: Path, compile_commands: Path | None, shim: Path) -> None:
        self.source = source
        self.shim = shim
        self.kind = "synthesized"
        self.units: dict[str, Unit] = {}  # source file -> unit holding it
        self.alt_units: dict[str, list[Unit]] = {}  # a file compiled twice with different defines
        self.by_dir: dict[str, list[str]] = {}
        self.build_dir: Path | None = None
        if compile_commands and compile_commands.exists():
            self.kind = f"compile_commands ({compile_commands})"
            self.build_dir = compile_commands.parent
            self._load(compile_commands)
        self._synth: list[str] | None = None
        self.missing_generated: list[str] = []
        self._make_shim()

    def _load(self, path: Path) -> None:
        entries = json.loads(path.read_text())
        include_re = re.compile(r'^#include "([^"]+)"', re.MULTILINE)
        for e in entries:
            file = e["file"]
            args = _clean(e.get("command") or e.get("arguments"), file)
            if "/Unity/unity_" in file:
                try:
                    included = include_re.findall(Path(file).read_text())
                except OSError:
                    continue
                unit = Unit(file, args, included)
                for inc in included:
                    self.units.setdefault(inc, unit)
                    self.by_dir.setdefault(str(Path(inc).parent), args)
                continue
            if file in self.units:  # the first entry is primary (rna_define.cc: makesrna, then bf_rna's runtime half)
                if file.endswith("rna_define.cc"):
                    self.alt_units.setdefault(file, []).append(Unit(file, args + ["-DSOURCE_STUBS_ALT"], [file]))
                continue
            self.units[file] = Unit(file, args, [file])
            self.by_dir.setdefault(str(Path(file).parent), args)

    def synthesized_args(self) -> list[str]:
        if self._synth is None:
            dirs: set[str] = set()
            # Skip directories with a header that shadows a system one (``intern/cycles/kernel/features.h`` hides
            # glibc's ``<features.h>``, a fatal error in every unit that reaches it).
            system = {
                "features.h",
                "types.h",
                "math.h",
                "string.h",
                "time.h",
                "limits.h",
                "stdint.h",
                "assert.h",
                "float.h",
                "memory.h",
                "version.h",
                "config.h",
            }
            for top in ("source/blender", "intern", "extern"):
                for header in (self.source / top).rglob("*.h*"):
                    if header.suffix in (".h", ".hh", ".hpp"):
                        dirs.add(str(header.parent))
            dirs = {d for d in dirs if not any((Path(d) / name).exists() for name in system)}
            # Generated-file-free roots that headers include relative to (``util/types.h`` for cycles).
            dirs.add(str(self.source / "intern/cycles"))
            args = ["-x", "c++", "-std=c++20"]
            args += [f"-D{d}" for d in SYNTH_DEFINES]
            args += [f"-I{d}" for d in sorted(dirs)]
            # Third-party headers (fmt, tbb, Python): Blender's precompiled libraries when present; else at least
            # this interpreter's Python headers.
            libs = precompiled_libraries()
            python = sorted(libs.glob("python/include/python3*"))
            args += ["-isystem", str(python[-1]) if python else sysconfig.get_paths()["include"]]
            for include in sorted(libs.glob("*/include")):
                args += ["-isystem", str(include)]
            self._synth = args
        return self._synth

    def _make_shim(self) -> None:
        """Declarations for generated headers the build has not produced (yet)."""
        self.shim.mkdir(parents=True, exist_ok=True)
        gen = self.build_dir / "source/blender/makesrna" if self.build_dir else None
        if gen and (gen / "RNA_prototypes.hh").exists():
            (self.shim / "RNA_prototypes.hh").unlink(missing_ok=True)  # written before the codegen ran
        else:
            # Same shape as makesrna's output: ``extern StructRNA *RNA_X;`` and ``extern PropertyRNA &rna_X_y;``.
            names: set[str] = set()
            props: set[str] = set()
            pat = re.compile(r"\bRNA_([A-Z][A-Za-z0-9]*)\b")
            prop_pat = re.compile(r"\brna_([A-Z][A-Za-z0-9]*_[a-z]\w*)\b")
            for path in (self.source / "source/blender").rglob("*.c*"):
                try:
                    text = path.read_text(errors="replace")
                except OSError:
                    continue
                # The makesrna files name RNA_X without including the header: their runtime halves are compiled
                # through rna_*_gen.cc, which includes it first.
                if "RNA_prototypes.hh" not in text and "/makesrna/" not in str(path):
                    continue
                names.update(pat.findall(text))
                if "/makesrna/" not in str(path):
                    props.update(prop_pat.findall(text))
            lines = ["#pragma once", "namespace blender {", "struct PropertyRNA;", "struct StructRNA;"]
            lines += [f"extern StructRNA *RNA_{n};" for n in sorted(names) if not n.isupper()]
            lines += [f"extern PropertyRNA &rna_{n};" for n in sorted(props)]
            lines.append("}  // namespace blender")
            (self.shim / "RNA_prototypes.hh").write_text("\n".join(lines) + "\n")
            self.missing_generated.append("RNA_prototypes.hh")
        if self.build_dir and (self.build_dir / "source/blender/makesdna/intern/dna_type_offsets.h").exists():
            (self.shim / "dna_type_offsets.h").unlink(missing_ok=True)
        else:
            (self.shim / "dna_type_offsets.h").write_text("#pragma once\nenum eDNA_StructId { SDNA_TYPE_MAX };\n")
            self.missing_generated.append("dna_type_offsets.h")

    def tail(self) -> list[str]:
        # Clang's default error limit (20) is fatal: everything after it in the unit would be lost.
        return ["-isystem", RESOURCE_INCLUDE, f"-I{self.shim}", "-Wno-everything", "-ferror-limit=0"]

    def runtime_unit(self, file: Path) -> Unit:
        """``rna_X.cc`` / ``rna_X_api.cc`` as bf_rna compiles them: through ``rna_X_gen.cc``, which defines
        ``RNA_RUNTIME``, has the target's include paths and includes ``RNA_prototypes.hh``, then both files.

        With the codegen done (``blender:build --target codegen``) the generated unit itself is parsed, once for
        both files. Without it, each file is parsed alone with the generated unit's flags and the shim."""
        stem = file.stem.removesuffix("_api")
        gen = self.build_dir / "source/blender/makesrna/intern" / f"{stem}_gen.cc" if self.build_dir else None
        unit = self.units.get(str(gen)) if gen else None
        if unit is not None and gen is not None and gen.exists():
            halves = [file.with_name(f"{stem}.cc"), file.with_name(f"{stem}_api.cc")]
            return Unit(str(gen), [*unit.args, *self.tail()], [str(f) for f in halves if f.exists()])
        if unit is not None:
            args = list(unit.args)
        else:
            args = [*self.unit_for(file).args, "-DRNA_RUNTIME"]
        args += ["-include", "RNA_prototypes.hh", *self.tail()]
        args += [f"-DSOURCE_STUBS_SHIM_{name.replace('.', '_')}" for name in self.missing_generated]
        return Unit(str(file), args, [str(file)])

    def units_for(self, file: Path) -> list[Unit]:
        tail = self.tail()
        alts = [Unit(u.path, [*u.args, *tail], list(u.files)) for u in self.alt_units.get(str(file), [])]
        return [self.unit_for(file), *alts]

    def unit_for(self, file: Path) -> Unit:
        key = str(file)
        tail = self.tail()
        tail += [f"-DSOURCE_STUBS_SHIM_{name.replace('.', '_')}" for name in self.missing_generated]
        unit = self.units.get(key)
        if unit is not None:
            return Unit(unit.path, [*unit.args, *tail], list(unit.files))
        # Not built in this configuration: borrow a sibling's flags, else synthesize.
        args = self.by_dir.get(str(file.parent)) or self.by_dir.get(str(file.parent.parent))
        if args is None:  # a header above its sources (DEG_depsgraph_query.hh over depsgraph/intern/)
            below = sorted(d for d in self.by_dir if d.startswith(f"{file.parent}/"))
            if below:
                args = self.by_dir[below[0]]
        if args is None:
            args = self.synthesized_args()
        if not any(a == "-x" for a in args):
            args = ["-x", "c++", "-std=c++20", *args] if file.suffix != ".c" else args
        return Unit(key, [*args, *tail], [key])
