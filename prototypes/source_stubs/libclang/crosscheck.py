"""Cross-check the return classifier (``returns.py``) with two independent tools, on the generated RNA units.

Both need the real ``rna_X_gen.cc`` units (``blender:build --target codegen``) and compile each with its flags from
``compile_commands.json``, cached per unit:

- **LLVM** (``clang -O1 -fno-inline -emit-llvm``): LLVM's own attribute inference marks a pointer return
  ``nonnull`` only when it proves it within the unit (an address, ``new``, a checked fallback, a dereferenced
  pointer). It is a proof of ``never`` for raw pointer returns; a ``PointerRNA`` returned by value (``sret``) has no
  attribute to read.
- **Clang Static Analyzer** (``clang --analyze``): a probe file includes the unit and calls each RNA function with
  its never-null arguments (``rna_arguments``), then dereferences the result (``.data`` of a ``PointerRNA``). A
  ``core.NullDereference`` there is a concrete path to a NULL return. The probe turns ``BKE_report`` /
  ``BKE_reportf`` into a sink for error levels: a NULL after one raises in Python, so it is no witness.
  ``suppress-null-return-paths`` is off: by default the analyzer hides exactly these paths.

Neither replaces the classifier: LLVM proves only what it sees in one unit, and the analyzer finds paths, never
their absence (callees in other units are opaque to both). A disagreement is a lead to inspect:

- LLVM proves non-null, the classifier says ``null`` or ``unknown``: a missed ``never`` (or an LLVM inference from
  undefined behaviour, such as a dereference before the return).
- The analyzer finds a NULL path, the classifier says ``never`` or ``raises``: a wrong verdict, or an analyzer
  false positive.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import shlex
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from libclang.returns import NEVER, NULL, RAISES, UNKNOWN, rna_arguments

CLANG = "/usr/bin/clang++"
CROSSCHECK_VERSION = 4
POINTER, POINTER_RNA = "pointer", "PointerRNA"  # how a C function returns: a raw pointer, or a PointerRNA by value


@dataclass(frozen=True)
class Probe:
    qual: str  # the C function, qualified (``blender::rna_Palette_color_new``)
    mask: int  # bit i: argument i is never NULL
    kind: str  # POINTER or POINTER_RNA

    @property
    def name(self) -> str:
        return self.qual.split("::")[-1]


@dataclass
class CheckUnit:
    """One generated unit to check: its compile entry, a probe per C function, the sources it compiles."""

    entry: dict
    probes: list[Probe] = field(default_factory=list)
    sources: list[Path] = field(default_factory=list)


# Before the unit: an error report ends the path (it raises in Python: pyrna_func_call -> BPy_reports_to_error).
# The analyzer never inlines a variadic function, so ``BKE_reportf`` cannot be given a body: both become macros
# calling a sink, after ``BKE_report.hh`` declared them (its ``#pragma once`` keeps the unit from redeclaring them).
REPORTS = """
#include "BKE_report.hh"
namespace blender {
inline void source_stubs_report(ReportList * /*reports*/, eReportType type)
{
  if (type >= RPT_ERROR) {
    __builtin_unreachable();
  }
}
}  // namespace blender
#define BKE_report(reports, type, ...) ::blender::source_stubs_report((reports), (type))
#define BKE_reportf(reports, type, ...) ::blender::source_stubs_report((reports), (type))
"""

PRELUDE = """
#include <cstddef>
#include <type_traits>
#include <utility>
namespace source_stubs_probe {
template<class T> T any();
template<class T> T arg(bool nonnull)
{
  T v = any<T>();
  if constexpr (std::is_pointer_v<T>) {
    if (nonnull && v == nullptr) {
      __builtin_unreachable();
    }
  }
  return v;
}
template<unsigned long long Mask, class R, class... A, std::size_t... I>
R call(R (*f)(A...), std::index_sequence<I...>)
{
  return f(arg<A>((Mask >> I) & 1)...);
}
template<unsigned long long Mask, class R, class... A> R call(R (*f)(A...))
{
  return call<Mask>(f, std::index_sequence_for<A...>{});
}
}  // namespace source_stubs_probe
"""


def probe_source(gen: str, probes: list[Probe]) -> tuple[str, dict[int, int]]:
    """The probe file for ``gen`` and, per line holding a dereference, the index of its probe."""
    lines = [*REPORTS.strip("\n").splitlines(), f'#include "{gen}"', *PRELUDE.strip("\n").splitlines()]
    at: dict[int, int] = {}
    for i, p in enumerate(probes):
        call = f"source_stubs_probe::call<{p.mask}ull>(&{p.qual})"
        target = f"{call}.data" if p.kind == POINTER_RNA else call
        lines.append(f"void source_stubs_probe_{i}() {{ (void)*(volatile const char *)({target}); }}")
        at[len(lines)] = i
    return "\n".join(lines) + "\n", at


def nonnull_returns(ll: str, names: list[str]) -> dict[str, tuple[bool, int | None]]:
    """For each name defined in the IR with a pointer return: whether LLVM marked the return ``nonnull``, and which
    argument it marked ``returned`` (the function returns that argument), if any.

    In a mangled symbol the name follows its length (``L17rna_Curve_spl_new``), which delimits it. Entities local to
    a function (``_ZZ...``: its lambdas, its statics) carry the function's name too and are skipped."""
    out: dict[str, tuple[bool, int | None]] = {}
    wanted = {n: re.compile(rf"(?<![0-9]){len(n)}{re.escape(n)}|^{re.escape(n)}$") for n in names}
    for line in ll.splitlines():
        m = re.match(r"define (.*?)@([\w.$]+)\((.*)\)", line)
        if not m or not re.search(r"\bptr\s*$", m[1]) or m[2].startswith("_ZZ"):
            continue
        returned = next((k for k, param in enumerate(m[3].split(", ")) if " returned " in f" {param} "), None)
        for n, pat in wanted.items():
            if n not in out and pat.search(m[2]):
                out[n] = ("nonnull" in m[1].split(), returned)
    return out


def witnesses(sarif: str, at: dict[int, int], probe_name: str) -> set[int]:
    """The probes the analyzer found a NULL dereference in."""
    found: set[int] = set()
    for run in json.loads(sarif).get("runs", []):
        for r in run.get("results", []):
            if r.get("ruleId") != "core.NullDereference":
                continue
            for loc in r.get("locations", []):
                phys = loc.get("physicalLocation", {})
                if not phys.get("artifactLocation", {}).get("uri", "").endswith(probe_name):
                    continue
                line = phys.get("region", {}).get("startLine")
                if line in at:
                    found.add(at[line])
    return found


def disagreements(rows: list[tuple[str, str, bool | None, bool | None]]) -> list[tuple[str, str]]:
    """``(function, verdict, llvm nonnull, analyzer witness)`` rows -> the findings that contradict the verdict."""
    out = []
    for name, verdict, llvm, csa in rows:
        if llvm and verdict in (NULL, UNKNOWN):
            out.append((name, f"LLVM proves the return non-null; classified {verdict}"))
        if csa and verdict in (NEVER, RAISES):
            out.append((name, f"the analyzer found a path to a NULL return; classified {verdict}"))
    return out


# --------------------------------------------------------------------------------------------------------------------
# Running clang


def _command(entry: dict) -> list[str]:
    """The unit's compile command without its output, optimization, debug or source arguments."""
    parts = shlex.split(entry["command"]) if "command" in entry else list(entry["arguments"])
    out, skip = [CLANG], False
    for a in parts[1:]:
        if skip:
            skip = False
            continue
        if a in ("-o", "-MF", "-MT", "-MQ"):
            skip = True
            continue
        if a == entry["file"] or a.startswith(("-O", "-g")) or a in ("-c", "-MD", "-MMD"):
            continue
        out.append(a)
    return out


def failed_probes(stderr: str, probe_name: str, at: dict[int, int]) -> set[int]:
    """The probes whose line has a compile error."""
    lines = {int(m[1]) for m in re.finditer(rf"{re.escape(probe_name)}:(\d+):\d+: error:", stderr)}
    return {at[n] for n in lines if n in at}


def _first_errors(stderr: str) -> str:
    errors = [line for line in stderr.splitlines() if " error: " in line or line.startswith("error:")]
    return " | ".join(errors[:3])[:600] or stderr.strip()[-300:]


def _check_unit(entry: dict, probes: list[Probe], work: str) -> dict:
    gen = entry["file"]
    stem = Path(gen).stem
    base = _command(entry)
    result: dict = {"unit": gen, "llvm": {}, "csa": [], "probed": [], "errors": []}
    ll = Path(work) / f"{stem}.ll"
    proc = subprocess.run(
        [*base, "-w", "-O1", "-fno-inline", "-emit-llvm", "-S", "-o", str(ll), gen],
        cwd=entry["directory"],
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        found = nonnull_returns(ll.read_text(errors="replace"), [p.name for p in probes])
        ll.unlink()
        for p in probes:
            if p.name in found:
                nonnull, returned = found[p.name]
                # Returning an argument the caller guarantees non-null is a non-null return too (``return self``).
                result["llvm"][p.qual] = nonnull or (returned is not None and bool(p.mask >> returned & 1))
    else:
        result["errors"].append(f"llvm: {_first_errors(proc.stderr)}")
    # A probe that does not compile (a C function whose name is overloaded) is dropped, and the unit runs again.
    for _attempt in range(3):
        if not probes:
            break
        text, at = probe_source(gen, probes)
        probe = Path(work) / f"{stem}_probe.cc"
        probe.write_text(text)
        sarif = Path(work) / f"{stem}.sarif"
        config = "suppress-null-return-paths=false,suppress-inlined-defensive-checks=false"
        proc = subprocess.run(
            [*base, "-w", "--analyze", "-Xclang", "-analyzer-config", "-Xclang", config]
            + ["--analyzer-output", "sarif", "-o", str(sarif), str(probe)],
            cwd=entry["directory"],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0 and sarif.exists():
            result["csa"] = sorted(probes[i].qual for i in witnesses(sarif.read_text(), at, probe.name))
            result["probed"] = [p.qual for p in probes]
            sarif.unlink()
            probe.unlink()
            break
        bad = failed_probes(proc.stderr, probe.name, at)
        if not bad:
            result["errors"].append(f"analyzer: {_first_errors(proc.stderr)}")
            break
        result["unprobed"] = result.get("unprobed", []) + [probes[i].qual for i in sorted(bad)]
        probes = [p for i, p in enumerate(probes) if i not in bad]
    else:
        result["errors"].append("analyzer: probes kept failing to compile")
    return result


def run(units: list[CheckUnit], cache: Path, jobs: int, log=print) -> list[dict]:
    """Check each unit, cached per its compile command, probes and the content of the files it compiles (the
    headers they include are not part of the key)."""
    cache.mkdir(parents=True, exist_ok=True)
    results: list[dict | None] = []
    todo = []
    for i, unit in enumerate(units):
        command = json.dumps(unit.entry.get("command") or unit.entry.get("arguments"))
        h = hashlib.sha1(f"{CROSSCHECK_VERSION}\0{CLANG}\0{command}\0{unit.probes}".encode())
        for f in [Path(unit.entry["file"]), *unit.sources]:
            h.update(f.read_bytes() if f.exists() else b"")
        out = cache / f"{Path(unit.entry['file']).stem}-{h.hexdigest()[:20]}.json.gz"
        if out.exists():
            results.append(json.loads(gzip.decompress(out.read_bytes())))
        else:
            results.append(None)
            todo.append((i, out))
    log(f"crosscheck: {len(units)} units ({len(todo)} to check, {len(units) - len(todo)} cached)")
    work = cache / "work"
    work.mkdir(exist_ok=True)
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(_check_unit, units[i].entry, units[i].probes, str(work)): (i, out) for i, out in todo}
        for done, fut in enumerate(as_completed(futures), 1):
            i, out = futures[fut]
            try:
                res = fut.result()
            except Exception as exc:  # one unit failing is a finding, not the end of the run
                res = {"unit": units[i].entry["file"], "llvm": {}, "csa": [], "probed": [], "errors": [repr(exc)]}
            else:
                out.write_bytes(gzip.compress(json.dumps(res).encode()))
            results[i] = res
            if done % 10 == 0 or done == len(todo):
                log(f"  checked {done}/{len(todo)}")
    return [r for r in results if r is not None]


# --------------------------------------------------------------------------------------------------------------------
# Driving it over the classified RNA functions


def classified(model, program):
    """``(struct, function, C function)`` for every RNA function the classifier gave a verdict with a C body."""
    for s in model.structs:
        for f in s.functions:
            fn = program.function(f.c_function, "") if f.returns_null and f.c_function else None
            if fn is not None:
                yield s, f, fn


def plan(model, program, compile_commands: Path, source: Path) -> list[CheckUnit]:
    """Group the classified RNA functions by the generated unit that compiles their C function."""
    by_file = {e["file"]: e for e in json.loads(compile_commands.read_text())}
    gen_dir = compile_commands.parent / "source/blender/makesrna/intern"
    units: dict[str, CheckUnit] = {}
    for _s, f, fn in classified(model, program):
        if "/makesrna/intern/rna_" not in fn.file:
            continue
        stem = Path(fn.file).stem.removesuffix("_api")
        gen = gen_dir / f"{stem}_gen.cc"
        entry = by_file.get(str(gen))
        kind = POINTER if fn.ret.rstrip().endswith("*") else POINTER_RNA if "PointerRNA" in fn.ret else ""
        if entry is None or not gen.exists() or not kind:
            continue
        unit = units.setdefault(
            str(gen), CheckUnit(entry, [], [source / Path(fn.file).with_name(f"{stem}{x}.cc") for x in ("", "_api")])
        )
        if any(p.qual == fn.qual for p in unit.probes):
            continue
        never_null = rna_arguments(f, fn.params)
        unit.probes.append(Probe(fn.qual, sum(1 << i for i, a in enumerate(never_null) if a == NEVER), kind))
    return [units[k] for k in sorted(units)]


def report(model, program, results: list[dict]) -> tuple[str, dict[str, int]]:
    """``crosscheck.md``, and its counts for the coverage table."""
    llvm: dict[str, bool] = {}  # by qualified C function: static functions of the same name differ per unit
    csa: set[str] = set()
    checked: set[str] = set()
    errors = [(r["unit"], e) for r in results for e in r.get("errors", [])]
    for r in results:
        llvm.update(r.get("llvm", {}))
        csa.update(r.get("csa", []))
        if not any(e.startswith("analyzer") for e in r.get("errors", [])):
            checked.update(r.get("probed", []))
    rows = []
    for s, f, fn in classified(model, program):
        witness = fn.qual in csa if fn.qual in checked else None
        rows.append((f"{s.identifier}.{f.identifier}", f.returns_null, llvm.get(fn.qual), witness, f.c_function))
    found = disagreements([r[:4] for r in rows])
    counts = {
        "rna_returns_llvm_nonnull": sum(1 for r in rows if r[2]),
        "rna_returns_llvm_checked": sum(1 for r in rows if r[2] is not None),
        "rna_returns_csa_witness": sum(1 for r in rows if r[3]),
        "rna_returns_csa_checked": sum(1 for r in rows if r[3] is not None),
        "rna_returns_crosscheck_disagreements": len(found),
    }
    lines = [
        "# Cross-checks of the RNA pointer returns",
        "",
        (
            "See `prototypes/source_stubs/libclang/crosscheck.py`. LLVM: `nonnull` inferred on the C function's "
            "return (raw pointer returns only). Analyzer: a path to a NULL return that no error report ends. "
            "Only RNA functions whose C body was parsed have a row."
        ),
        "",
        "| Verdict | Functions | LLVM checked | LLVM nonnull | Analyzer checked | Analyzer NULL path |",
        "|---|---|---|---|---|---|",
    ]
    for kind in (NEVER, RAISES, NULL, UNKNOWN):
        mine = [r for r in rows if r[1] == kind]
        lines.append(
            f"| {kind} | {len(mine)} | {sum(r[2] is not None for r in mine)} | {sum(bool(r[2]) for r in mine)} "
            f"| {sum(r[3] is not None for r in mine)} | {sum(bool(r[3]) for r in mine)} |"
        )
    lines += ["", f"## Disagreements ({len(found)})", "", "| Function | C function | Finding |", "|---|---|---|"]
    c_of = {r[0]: r[4] for r in rows}
    lines += [f"| `{name}` | `{c_of[name]}` | {why} |" for name, why in sorted(found)]
    unprobed = sorted({q for r in results for q in r.get("unprobed", [])})
    lines += [
        "",
        f"Not probed (the probe did not compile, e.g. an overloaded name): {', '.join(f'`{q}`' for q in unprobed) or 'none'}",
    ]
    lines += ["", f"## Units the tools could not compile ({len(errors)})", ""]
    lines += [f"- `{Path(u).name}`: {e.splitlines()[0][:200] if e else ''}" for u, e in errors]
    return "\n".join(lines) + "\n", counts
