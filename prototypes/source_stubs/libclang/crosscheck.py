"""Cross-check the return classifier (``returns.py``) with two independent tools, on the generated RNA units.

Both need the real ``rna_X_gen.cc`` units (``blender:build --target codegen``) and compile each with its flags from
``compile_commands.json``, cached per unit:

- **LLVM** (``clang -O1 -fno-inline -emit-llvm``): LLVM's own attribute inference marks a pointer return
  ``nonnull`` only when it proves it within the unit (an address, ``new``, a checked fallback, a dereferenced
  pointer). It is a proof of ``never`` for raw pointer returns; a ``PointerRNA`` returned by value (``sret``) has no
  attribute to read.
- **Clang Static Analyzer** (``clang --analyze``): a probe file includes the unit and calls each RNA function with
  its never-null arguments (``rna_arguments``), then dereferences the result (``.data`` of a ``PointerRNA``). A
  ``core.NullDereference`` there is a concrete path to a NULL return. The probe defines ``BKE_report`` /
  ``BKE_reportf`` so that an error report ends the path: a NULL after one raises in Python, so it is no witness.
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
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

CLANG = "/usr/bin/clang++"
CROSSCHECK_VERSION = 1


@dataclass(frozen=True)
class Probe:
    qual: str  # the C function, qualified (``blender::rna_Palette_color_new``)
    mask: int  # bit i: argument i is never NULL
    kind: str  # "pointer" or "PointerRNA"


PRELUDE = """
#include <cstddef>
#include <type_traits>
#include <utility>
namespace blender {
/* An error report raises in Python (pyrna_func_call -> BPy_reports_to_error): end the path there. */
void BKE_report(ReportList *reports, eReportType type, const char *message)
{
  (void)reports;
  (void)message;
  if (type >= RPT_ERROR) {
    __builtin_unreachable();
  }
}
void BKE_reportf(ReportList *reports, eReportType type, const char *format, ...)
{
  (void)reports;
  (void)format;
  if (type >= RPT_ERROR) {
    __builtin_unreachable();
  }
}
}  // namespace blender
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
    lines = [f'#include "{gen}"', *PRELUDE.strip("\n").splitlines()]
    at: dict[int, int] = {}
    for i, p in enumerate(probes):
        call = f"source_stubs_probe::call<{p.mask}ull>(&{p.qual})"
        target = f"{call}.data" if p.kind == "PointerRNA" else call
        lines.append(f"void source_stubs_probe_{i}() {{ (void)*(volatile const char *)({target}); }}")
        at[len(lines)] = i
    return "\n".join(lines) + "\n", at


def nonnull_returns(ll: str, names: list[str]) -> dict[str, bool]:
    """For each name defined in the IR with a pointer return: whether LLVM marked the return ``nonnull``. In a
    mangled symbol the name follows its length (``L17rna_Curve_spl_new``), which delimits it."""
    out: dict[str, bool] = {}
    wanted = {n: re.compile(rf"(?<![0-9]){len(n)}{re.escape(n)}|^{re.escape(n)}$") for n in names}
    for line in ll.splitlines():
        if not line.startswith("define "):
            continue
        m = re.match(r"define (.*?)@([\w.$]+)\(", line)
        if not m or not re.search(r"\bptr\s*$", m[1]):
            continue
        symbol = m[2]
        for n, pat in wanted.items():
            if pat.search(symbol):
                out[n] = "nonnull" in m[1].split()
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
        if llvm and verdict in ("null", "unknown"):
            out.append((name, f"LLVM proves the return non-null; classified {verdict}"))
        if csa and verdict in ("never", "raises"):
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
        if a in ("-o", "-c", "-MF", "-MT", "-MQ"):
            skip = True
            continue
        if a == entry["file"] or a.startswith(("-O", "-g")) or a in ("-MD", "-MMD"):
            continue
        out.append(a)
    return out


def _check_unit(entry: dict, names: list[str], probes: list[Probe], work: str) -> dict:
    gen = entry["file"]
    stem = Path(gen).stem
    base = _command(entry)
    result: dict = {"unit": gen, "llvm": {}, "csa": [], "probed": [p.qual for p in probes], "errors": []}
    ll = Path(work) / f"{stem}.ll"
    proc = subprocess.run(
        [*base, "-w", "-O1", "-fno-inline", "-emit-llvm", "-S", "-o", str(ll), gen],
        cwd=entry["directory"],
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        result["llvm"] = nonnull_returns(ll.read_text(errors="replace"), names)
        ll.unlink()
    else:
        result["errors"].append(f"llvm: {proc.stderr.strip()[-400:]}")
    if probes:
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
            sarif.unlink()
        else:
            result["errors"].append(f"analyzer: {proc.stderr.strip()[-400:]}")
    return result


def run(units: list[tuple[dict, list[str], list[Probe], list[Path]]], cache: Path, jobs: int, log=print) -> list[dict]:
    """Check each ``(compile entry, C function names, probes, source files)``; cached per unit and content."""
    cache.mkdir(parents=True, exist_ok=True)
    results: list[dict | None] = []
    todo = []
    for i, (entry, names, probes, sources) in enumerate(units):
        h = hashlib.sha1(f"{CROSSCHECK_VERSION}\0{entry.get('command')}\0{names}\0{probes}".encode())
        for f in [Path(entry["file"]), *sources]:
            h.update(f.read_bytes() if f.exists() else b"")
        out = cache / f"{Path(entry['file']).stem}-{h.hexdigest()[:20]}.json.gz"
        if out.exists():
            results.append(json.loads(gzip.decompress(out.read_bytes())))
        else:
            results.append(None)
            todo.append((i, out))
    log(f"crosscheck: {len(units)} units ({len(todo)} to check, {len(units) - len(todo)} cached)")
    work = cache / "work"
    work.mkdir(exist_ok=True)
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(_check_unit, units[i][0], units[i][1], units[i][2], str(work)): (i, out) for i, out in todo}
        for done, fut in enumerate(futures, 1):
            i, out = futures[fut]
            res = fut.result()
            out.write_bytes(gzip.compress(json.dumps(res).encode()))
            results[i] = res
            if done % 10 == 0 or done == len(todo):
                log(f"  checked {done}/{len(todo)}")
    return [r for r in results if r is not None]


# --------------------------------------------------------------------------------------------------------------------
# Driving it over the classified RNA functions


def plan(model, program, compile_commands: Path, source: Path) -> list[tuple[dict, list[str], list[Probe], list[Path]]]:
    """Group the classified RNA functions by the generated unit that compiles their C function."""
    from libclang.returns import NEVER, rna_arguments

    by_file = {e["file"]: e for e in json.loads(compile_commands.read_text())}
    gen_dir = compile_commands.parent / "source/blender/makesrna/intern"
    units: dict[str, tuple[dict, list[str], list[Probe], list[Path]]] = {}
    for s in model.structs:
        for f in s.functions:
            if not f.returns_null or not f.c_function:
                continue
            fn = program.function(f.c_function, "")
            if fn is None or "/makesrna/intern/rna_" not in fn.file:
                continue
            stem = Path(fn.file).stem.removesuffix("_api")
            gen = gen_dir / f"{stem}_gen.cc"
            entry = by_file.get(str(gen))
            if entry is None or not gen.exists():
                continue
            if str(gen) not in units:
                halves = [source / Path(fn.file).with_name(f"{stem}{x}.cc") for x in ("", "_api")]
                units[str(gen)] = (entry, [], [], halves)
            _entry, names, probes, _halves = units[str(gen)]
            if fn.name in names:
                continue
            names.append(fn.name)
            kind = "pointer" if fn.ret.rstrip().endswith("*") else "PointerRNA" if "PointerRNA" in fn.ret else ""
            if kind:
                args = rna_arguments(f, fn.params)
                mask = sum(1 << i for i, a in enumerate(args) if a == NEVER)
                probes.append(Probe(fn.qual, mask, kind))
    return [units[k] for k in sorted(units)]


def report(model, program, results: list[dict]) -> tuple[str, dict[str, int]]:
    """``crosscheck.md``, and its counts for the coverage table."""
    llvm: dict[str, bool] = {}
    csa: set[str] = set()
    checked: set[str] = set()
    errors = [(r["unit"], e) for r in results for e in r.get("errors", [])]
    for r in results:
        llvm.update(r.get("llvm", {}))
        csa.update(r.get("csa", []))
        if not any(e.startswith("analyzer") for e in r.get("errors", [])):
            checked.update(r.get("probed", []))
    rows = []
    for s in model.structs:
        for f in s.functions:
            fn = program.function(f.c_function, "") if f.returns_null and f.c_function else None
            if fn is None:
                continue
            in_llvm = llvm.get(fn.name)
            witness = fn.qual in csa if fn.qual in checked else None
            rows.append((f"{s.identifier}.{f.identifier}", f.returns_null, in_llvm, witness, f.c_function))
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
        "See `prototypes/source_stubs/libclang/crosscheck.py`. LLVM: `nonnull` inferred on the C function's return "
        "(raw pointer returns only). Analyzer: a path to a NULL return that no error report ends.",
        "",
        "| Verdict | Functions | LLVM checked | LLVM nonnull | Analyzer checked | Analyzer NULL path |",
        "|---|---|---|---|---|---|",
    ]
    for kind in ("never", "raises", "null", "unknown"):
        mine = [r for r in rows if r[1] == kind]
        lines.append(
            f"| {kind} | {len(mine)} | {sum(r[2] is not None for r in mine)} | {sum(bool(r[2]) for r in mine)} "
            f"| {sum(r[3] is not None for r in mine)} | {sum(bool(r[3]) for r in mine)} |"
        )
    lines += ["", f"## Disagreements ({len(found)})", "", "| Function | C function | Finding |", "|---|---|---|"]
    c_of = {r[0]: r[4] for r in rows}
    lines += [f"| `{name}` | `{c_of[name]}` | {why} |" for name, why in sorted(found)]
    lines += ["", f"## Units the tools could not compile ({len(errors)})", ""]
    lines += [f"- `{Path(u).name}`: {e.splitlines()[0][:200] if e else ''}" for u, e in errors]
    return "\n".join(lines) + "\n", counts
