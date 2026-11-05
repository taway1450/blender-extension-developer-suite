# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Check the feature tests' markers against their reference stubs with stock ty (the oracle run).

The features in ``tests/typecheck/features/`` describe what ty-blender should synthesise, for example the
function behind ``bpy.ops.myaddon.move`` or the properties ``layout.operator("myaddon.move")`` returns. Each
addon writes that down as reference stubs in ``<addon>/_expected/``:

- ``_expected/addon/<path>.pyi``: stubs of the addon's own modules, placed next to the ``.py`` files;
- ``_expected/stubs/<module>.pyi`` (e.g. ``bpy.types.pyi``, ``bpy.ops.myaddon.pyi``): a delta merged into a
  copy of the bpy stubs. Members of a class that exists are added to it, an ``@overload`` of a function or
  method that exists is put in front of it (which then becomes the last overload), a member that exists is
  replaced, a class that states other bases or type parameters replaces the class, and anything else is appended.
  A module that does not exist is created.

Before the addon's deltas, the deltas in ``tests/typecheck/oracle/<generator>/`` are merged: what ty-blender
assumes about the bpy stubs of that generator (for example that ``bpy_prop_array`` is generic), so that the
addons' reference stubs can be the same for both generators.

Stock ty (``uvx ty@<version of ty-blender>``) then checks the addon against these copies, and every marker must
pass. That shows the markers are consistent and can be satisfied at all, before ty-blender implements anything.
Markers that only ty-blender can satisfy are left out: expected errors whose rules are all ``blender-*``, and
lines with an ``# oracle-skip: <reason>`` comment. Only ``check_*.py`` files are judged: the addon's own modules are
checked from their source, and their idiomatic code (``x: IntProperty()``) is what ty-blender has to understand.

Then the bare run: stock ty on the addons with the bpy stubs alone (no baseline, no reference stubs), which shows that
the markers need the checker. A marker that still holds there on every generator (``bare_hits``) tests nothing of
ty-blender, unless it is a guard marked ``# bare-ok: <reason>``, and fails the task. A run of one ``--generator``
only reports the bare run's hits, since it cannot tell whether they hold on the other generators.

Results go to ``.cache/typecheck-results/<version>/<generator>/oracle.md``; the task fails on any oracle failure.

Usage:
  uv run scripts/check_oracle.py main
  uv run scripts/check_oracle.py main operator_calls --generator builtin
"""

from __future__ import annotations

import argparse
import ast
import os
import shutil
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path

from _common import CACHE_DIR, TYPECHECK_TESTS_DIR, StepError, log, main_wrapper
from _features import FEATURES_DIR, Addon, AddonResult, MarkerResult, evaluate, parse_diagnostics, select
from _markers import UNKNOWN_RULE, is_check_file
from _target import Target, add_target_arguments
from build_ty import stock_command
from generate_stubs import ALL

ORACLE_DIR = CACHE_DIR / "typecheck-oracle"
BASELINE_DIR = TYPECHECK_TESTS_DIR / "oracle"


# --- merging reference-stub deltas into the bpy stubs ------------------------------------------------------------


def module_file(stubs: Path, module: str) -> Path | None:
    """The stub file of ``module`` in either layout (``bpy/types/__init__.pyi`` or ``bpy-stubs/types/...``)."""
    head, *rest = module.split(".")
    for top in (head, f"{head}-stubs"):
        base = stubs.joinpath(top, *rest)
        for candidate in (base / "__init__.pyi", base.with_suffix(".pyi")):
            if candidate.is_file():
                return candidate
    return None


def new_module_file(stubs: Path, module: str) -> Path:
    parent, _, name = module.rpartition(".")
    parent_file = module_file(stubs, parent) if parent else None
    if parent_file is None or parent_file.name != "__init__.pyi":
        raise StepError(f"Cannot create stub module {module}: its parent package {parent!r} is not in {stubs}")
    return parent_file.parent / f"{name}.pyi"


def node_start(node: ast.stmt) -> int:
    """0-based first line of a statement, decorators included."""
    decorators = getattr(node, "decorator_list", [])
    return min([node.lineno, *(d.lineno for d in decorators)]) - 1


def segment(lines: list[str], node: ast.stmt) -> str:
    return textwrap.dedent("\n".join(lines[node_start(node) : node.end_lineno]))


def is_overload(node: ast.stmt) -> bool:
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
        (isinstance(d, ast.Name) and d.id == "overload") or (isinstance(d, ast.Attribute) and d.attr == "overload")
        for d in node.decorator_list
    )


def member_name(node: ast.stmt) -> str | None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    return None


def indent(text: str, prefix: str) -> list[str]:
    return [prefix + line if line.strip() else line for line in text.splitlines()]


@dataclass
class Edit:
    start: int  # 0-based line; lines[start:end] are replaced by `lines`
    end: int
    lines: list[str]


def merge_members(
    body: list[ast.stmt],
    delta_body: list[ast.stmt],
    delta_lines: list[str],
    prefix: str,
    append_at: int,
    edits: list[Edit],
) -> bool:
    """Edits that merge ``delta_body`` into ``body`` (statements at indentation ``prefix``); returns whether an
    ``overload`` import is needed."""
    needs_overload = False
    by_name: dict[str, list[ast.stmt]] = {}
    for node in body:
        if (name := member_name(node)) is not None:
            by_name.setdefault(name, []).append(node)
    appended: list[str] = []
    overloads: dict[str, list[str]] = {}  # name -> delta overloads, in delta order, to put before the existing ones
    for node in delta_body:
        name = member_name(node)
        existing = by_name.get(name or "", [])
        text = indent(segment(delta_lines, node), prefix)
        if existing and is_overload(node):
            overloads.setdefault(name, []).extend(text)
        elif existing:
            for old in existing[1:]:
                edits.append(Edit(node_start(old), old.end_lineno, []))
            edits.append(Edit(node_start(existing[0]), existing[0].end_lineno, text))
        elif not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)):  # skip docstrings
            appended += text
    for name, insert in overloads.items():
        existing = by_name[name]
        if not any(is_overload(e) for e in existing):
            insert.append(f"{prefix}@overload")  # the existing definition becomes the last overload
            needs_overload = True
        edits.append(Edit(node_start(existing[0]), node_start(existing[0]), insert))
    if appended:
        edits.append(Edit(append_at, append_at, appended))
    return needs_overload


def class_header(node: ast.ClassDef) -> list[str]:
    params = [ast.unparse(p) for p in getattr(node, "type_params", [])]
    return params + [ast.unparse(b) for b in node.bases] + [ast.unparse(k) for k in node.keywords]


def merge_delta(stub_text: str, delta_text: str, stub_tree: ast.Module | None = None) -> str:
    lines = stub_text.splitlines()
    tree = stub_tree or ast.parse(stub_text)
    delta_lines = delta_text.splitlines()
    delta = ast.parse(delta_text)
    edits: list[Edit] = []
    imports = [segment(delta_lines, n) for n in delta.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    top_level: list[ast.stmt] = []
    needs_overload = False
    for node in delta.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if (
            isinstance(node, ast.ClassDef)
            and node.name in classes
            and class_header(node)
            and class_header(node) != class_header(classes[node.name])
        ):
            target = classes[node.name]
            edits.append(Edit(node_start(target), target.end_lineno, segment(delta_lines, node).splitlines()))
        elif isinstance(node, ast.ClassDef) and node.name in classes:
            target = classes[node.name]
            prefix = " " * target.body[0].col_offset
            needs_overload |= merge_members(target.body, node.body, delta_lines, prefix, target.end_lineno, edits)
        else:
            top_level.append(node)
    needs_overload |= merge_members(tree.body, top_level, delta_lines, "", len(lines), edits)
    if needs_overload:
        imports.append("from typing import overload")
    if imports:
        future = [n for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == "__future__"]
        after = future[-1].end_lineno if future else (1 if tree.body and isinstance(tree.body[0], ast.Expr) else 0)
        if tree.body and isinstance(tree.body[0], ast.Expr) and not future:
            after = tree.body[0].end_lineno  # after the module docstring
        edits.append(Edit(after, after, [line for imp in imports for line in imp.splitlines()]))
    # Apply from the bottom so that line numbers stay valid; inserts at the same line keep their order.
    for edit in sorted(edits, key=lambda e: (e.start, e.end), reverse=True):
        lines[edit.start : edit.end] = edit.lines
    return "\n".join(lines) + "\n"


class StubOverlay:
    """Copies of the top-level stub packages that deltas touch, with the deltas merged in; unchanged files are hard
    links. ``sources`` are the stub directories in search order: earlier overlays first, the bpy stubs last."""

    def __init__(self, sources: list[Path]) -> None:
        self.sources = sources
        self.trees: dict[Path, ast.Module] = {}

    def locate(self, module: str) -> tuple[Path, Path | None]:
        """The source directory that provides the module's top-level package, and the module's file in it."""
        top = module.split(".")[0]
        for source in self.sources:
            if (source / top).is_dir() or (source / f"{top}-stubs").is_dir():
                return source, module_file(source, module)
        raise StepError(f"No stubs provide the package of {module} (searched {', '.join(map(str, self.sources))})")

    def tree(self, path: Path) -> ast.Module:
        if path not in self.trees:
            self.trees[path] = ast.parse(path.read_text(encoding="utf-8"))
        return self.trees[path]

    def build(self, deltas: Path, target: Path) -> None:
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        for delta in sorted(deltas.glob("*.pyi")):
            module = delta.stem
            stubs, source = self.locate(module)
            top = (source or new_module_file(stubs, module)).relative_to(stubs).parts[0]
            if not (target / top).exists():
                link_tree(stubs / top, target / top)
            delta_text = delta.read_text(encoding="utf-8")
            if source is None:
                out = target / new_module_file(stubs, module).relative_to(stubs)
                out.write_text(delta_text, encoding="utf-8")
                continue
            out = target / source.relative_to(stubs)
            current = out.read_text(encoding="utf-8")
            tree = self.tree(source) if current == source.read_text(encoding="utf-8") else None
            merged = merge_delta(current, delta_text, tree)
            out.unlink()  # a hard link to the original stubs
            out.write_text(merged, encoding="utf-8")


def link_tree(source: Path, target: Path) -> None:
    def link(src: str, dst: str) -> None:
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)

    shutil.copytree(source, target, copy_function=link)


# --- the oracle project -------------------------------------------------------------------------------------------


def build_project(addon: Addon, target: Path) -> None:
    """A copy of tests/typecheck (ty.toml and all features, so imports of other addons resolve) with the addon's
    own reference stubs next to its modules."""
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    shutil.copy2(TYPECHECK_TESTS_DIR / "ty.toml", target / "ty.toml")
    shutil.copytree(FEATURES_DIR, target / "features", ignore=shutil.ignore_patterns("__pycache__"))
    own = addon.expected_stubs / "addon" if addon.expected_stubs else None
    if own and own.is_dir():
        addon_copy = target / addon.rel
        for stub in own.rglob("*.pyi"):
            out = addon_copy / stub.relative_to(own)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(stub, out)


def run_ty(cmd: list, cwd: Path) -> str:
    """ty's concise output; ty exits with 1 when it reports errors."""
    result = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode not in (0, 1):
        raise StepError(f"ty failed with exit code {result.returncode}:\n{result.stderr}")
    return result.stdout


@dataclass
class OracleResult:
    result: AddonResult
    checked: int
    failures: list[str]


def judge(result: AddonResult) -> OracleResult:
    skipped = {(path, line) for path, f in result.files.items() for line in f.oracle_skip_lines}
    failures = []
    checked = 0
    for m in result.markers:
        marker = m.marker
        if marker.blender_only or not marker.in_check_file or marker.oracle_skip:
            continue
        checked += 1
        if m.failures:  # other diagnostics on the line fail it below, as unexpected ones
            messages = "; ".join(d.message for d in m.failures)
            failures.append(f"FAIL `{marker.path}:{marker.line}` `{marker.source}`: {messages}")
    for d in result.unexpected:
        if is_check_file(d.path) and (d.path, d.line) not in skipped:
            failures.append(f"{d.severity}[{d.rule}] `{d.path}:{d.line}:{d.col}`: {d.message}")
    return OracleResult(result, checked, failures)


# --- the bare run -------------------------------------------------------------------------------------------------


def bare_hits(result: AddonResult) -> list[MarkerResult]:
    """Markers that claim to need ty-blender (``TypeMarker.needs_checker``) yet hold in the bare run: stock ty
    reported nothing on their line apart from unknown ``blender-*`` rules. An ``assert_type`` that passes but whose
    line has another error (an unresolved attribute, say) still needs the checker."""
    return [m for m in result.markers if m.marker.needs_checker and all(d.rule == UNKNOWN_RULE for d in m.diagnostics)]


BareKey = tuple[str, str]  # path and line key of a marker, the same on every generator


def bare_run(ty: list[str], addons: list[Addon], stubs: Path, python_version: str) -> dict[BareKey, MarkerResult]:
    """Stock ty on the add-ons as they are, with nothing but the bpy stubs: no oracle baseline, no reference stubs."""
    cmd = [
        *ty,
        "check",
        "--project",
        TYPECHECK_TESTS_DIR,
        "--python-version",
        python_version,
        "--extra-search-path",
        stubs,
        "--output-format",
        "concise",
        "--no-progress",
        *(a.path for a in addons),
    ]
    results = evaluate(addons, parse_diagnostics(run_ty(cmd, TYPECHECK_TESTS_DIR)))
    return {(m.marker.path, m.marker.key): m for r in results for m in bare_hits(r)}


def bare_markdown(
    generator: str, hits: dict[BareKey, MarkerResult], everywhere: set[BareKey], complete: bool
) -> list[str]:
    lines = [
        "",
        "## Bare run: markers that hold without ty-blender",
        "",
        f"Stock ty on the {generator} stubs alone. A marker that holds on every generator does not test the checker",
        "and fails the task: make it need the checker, drop it, or mark it `# bare-ok: <reason>`.",
        "",
    ]
    for key in sorted(hits):
        m = hits[key]
        if not complete:
            where = "not judged (one generator run)"
        else:
            where = "FAIL, every generator" if key in everywhere else "this generator only"
        lines.append(f"- {where}: `{m.marker.path}:{m.marker.line}` `{m.marker.source}`")
    if not hits:
        lines.append("None.")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_target_arguments(parser, binary=None)  # stock ty from PyPI, not ty-blender
    parser.add_argument(
        "features", nargs="*", help="Features or addons (`feature/addon`) in tests/typecheck/features/ (default: all)"
    )
    args = parser.parse_args()

    addons = [a for a in select(args.features) if a.type_test_files()]
    target = Target.from_args(args)
    python_version = target.python_version
    ty = stock_command("ty")

    failed = False
    bare: dict[str, dict[BareKey, MarkerResult]] = {}
    reports: dict[str, list[str]] = {}
    for generator, stubs in target.stubs.items():
        log(
            f"Oracle run: stock ty with reference stubs (Python {python_version}, Blender {args.version}, "
            f"{generator} stubs) on {len(addons)} addons"
        )
        work = ORACLE_DIR / args.version / generator
        base_paths = [stubs]
        if (BASELINE_DIR / generator).is_dir():
            StubOverlay([stubs]).build(BASELINE_DIR / generator, work / "_baseline")
            base_paths.insert(0, work / "_baseline")
        overlay = StubOverlay(base_paths)
        outcomes = []
        for addon in addons:
            project = work / addon.module / "project"
            build_project(addon, project)
            search_paths = list(base_paths)
            deltas = addon.expected_stubs / "stubs" if addon.expected_stubs else None
            if deltas and deltas.is_dir():
                overlay.build(deltas, work / addon.module / "stubs")
                search_paths.insert(0, work / addon.module / "stubs")
            cmd = [
                *ty,
                "check",
                "--project",
                project,
                "--python-version",
                python_version,
                "--output-format",
                "concise",
                "--no-progress",
                *(a for p in search_paths for a in ("--extra-search-path", p)),
                project / addon.rel,
            ]
            output = run_ty(cmd, project)
            (work / addon.module / "ty.txt").write_text(output, encoding="utf-8")
            [addon_result] = evaluate([addon], parse_diagnostics(output, base=project))
            outcome = judge(addon_result)
            outcomes.append(outcome)
            status = "ok" if not outcome.failures else f"{len(outcome.failures)} failures"
            print(f"    {addon.feature}/{addon.name}: {outcome.checked} markers checked, {status}", flush=True)

        lines = [
            f"# Oracle run: stock ty with reference stubs, {generator} stubs, Blender {args.version}",
            "",
            "| Feature | Addon | markers checked | failures |",
            "| --- | --- | --- | --- |",
        ]
        lines += [
            f"| {o.result.addon.feature} | {o.result.addon.name} | {o.checked} | {len(o.failures)} |" for o in outcomes
        ]
        for o in outcomes:
            if o.failures:
                lines += ["", f"## {o.result.addon.feature}/{o.result.addon.name}", "", *(f"- {f}" for f in o.failures)]
        total = sum(len(o.failures) for o in outcomes)
        log(f"{total} oracle failures")
        failed |= total > 0

        log(f"Bare run: stock ty on the {generator} stubs alone")
        bare[generator] = bare_run(ty, addons, stubs, python_version)
        reports[generator] = lines

    # A marker only fails to test the checker when it holds on every generator, so a run of one generator (when there
    # are more) can only report its hits.
    complete = args.generator == ALL
    everywhere = set.intersection(*(set(hits) for hits in bare.values())) if bare and complete else set()
    for generator, lines in reports.items():
        lines += bare_markdown(generator, bare[generator], everywhere, complete)
        path = target.results_dir(generator) / "oracle.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        log(f"{generator}: {len(bare[generator])} markers hold on the bare stubs; summary: {path}")
    if complete:
        log(f"{len(everywhere)} markers hold on the bare stubs of every generator")
        failed |= bool(everywhere)
    else:
        log(f"Bare run of --generator {args.generator} only: its hits are reported, not judged")
    return 1 if failed else 0


if __name__ == "__main__":
    main_wrapper(main)
