# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Type-check the feature tests in ``tests/typecheck/`` with ty and compare with the recorded results.

Every folder in ``tests/typecheck/features/`` is an extension: an idiomatic ``__init__.py`` plus a
``check_<feature>.py`` with markers (see ``tests/typecheck/README.md``):

- ``assert_type(expr, T)`` passes unless ty reports ``type-assertion-failure`` on its line;
- ``# ty: ignore[rule]`` (an expected error) passes unless ty reports ``unused-ignore-comment`` on its line;
- any other diagnostic is unexpected.

The results that are not passes go to ``tests/typecheck/expected/<generator>/<version>.txt``. The task fails
when they differ from that file, so both regressions and fixes show up; ``--update`` rewrites it. A summary per
feature and the full ty output go to ``.cache/typecheck-results/<version>/<generator>/``.

Usage:
  uv run scripts/check_features.py main                       # all features, both stub generators
  uv run scripts/check_features.py 5.2 props_annotations --generator fake-bpy-module
  uv run scripts/check_features.py main --update
"""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from _common import CACHE_DIR, TYPECHECK_TESTS_DIR, StepError, log, main_wrapper
from build_ty import build_ty
from generate_stubs import (
    add_stubs_arguments,
    blender_python_version,
    ensure_worktree,
    generate_stubs,
    resolve_generators,
)

FEATURES_DIR = TYPECHECK_TESTS_DIR / "features"
EXPECTED_DIR = TYPECHECK_TESTS_DIR / "expected"
RESULTS_DIR = CACHE_DIR / "typecheck-results"

# ty --output-format concise: `path:line:col: severity[rule] message`
DIAGNOSTIC = re.compile(r"^(?P<path>.+?):(?P<line>\d+):(?P<col>\d+): (?P<severity>\w+)\[(?P<rule>[\w-]+)\] (?P<message>.*)$")
ASSERT_MARKER = re.compile(r"\bassert_type\(")
IDE_PREFIX = "ide_"  # files for check:ide, not type tests
IGNORE_MARKER =re.compile(r"#\s*ty:\s*ignore\[(?P<rules>[^\]]+)\]")


@dataclass(frozen=True)
class Diagnostic:
    path: str  # relative to tests/typecheck, with forward slashes
    line: int
    col: int
    severity: str
    rule: str
    message: str


@dataclass
class Marker:
    path: str
    line: int
    kind: str  # "assert_type" or "expected-error"
    source: str
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def failure_rule(self) -> str:
        return "type-assertion-failure" if self.kind == "assert_type" else "unused-ignore-comment"

    @property
    def passed(self) -> bool:
        return not any(d.rule == self.failure_rule for d in self.diagnostics)


@dataclass
class FeatureResult:
    name: str
    markers: list[Marker]
    unexpected: list[Diagnostic]

    def counts(self, kind: str) -> tuple[int, int]:
        markers = [m for m in self.markers if m.kind == kind]
        return sum(m.passed for m in markers), len(markers)


def feature_names() -> list[str]:
    return sorted(p.name for p in FEATURES_DIR.iterdir() if (p / "__init__.py").is_file())


def find_markers(feature: str) -> list[Marker]:
    markers = []
    for path in sorted((FEATURES_DIR / feature).glob("*.py")):
        if path.name.startswith(IDE_PREFIX):
            continue
        rel = path.relative_to(TYPECHECK_TESTS_DIR).as_posix()
        for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if IGNORE_MARKER.search(text):
                markers.append(Marker(rel, number, "expected-error", text.strip()))
            elif ASSERT_MARKER.search(text) and not text.lstrip().startswith(("#", "from ", "import ")):
                markers.append(Marker(rel, number, "assert_type", text.strip()))
    return markers


def parse_diagnostics(output: str) -> list[Diagnostic]:
    diagnostics = []
    for text in output.splitlines():
        match = DIAGNOSTIC.match(text)
        if match:
            path = Path(match["path"])
            if path.is_absolute():
                path = path.relative_to(TYPECHECK_TESTS_DIR)
            diagnostics.append(Diagnostic(path.as_posix(), int(match["line"]), int(match["col"]), match["severity"],
                                          match["rule"], match["message"]))
    return diagnostics


def evaluate(features: list[str], diagnostics: list[Diagnostic]) -> list[FeatureResult]:
    results = []
    for feature in features:
        markers = find_markers(feature)
        by_line = {(m.path, m.line): m for m in markers}
        unexpected = []
        for diagnostic in diagnostics:
            if not diagnostic.path.startswith(f"features/{feature}/"):
                continue
            if diagnostic.path.rpartition("/")[2].startswith(IDE_PREFIX):
                continue  # editor tests (check:ide) hold unfinished code on purpose
            marker = by_line.get((diagnostic.path, diagnostic.line))
            if marker is not None:
                marker.diagnostics.append(diagnostic)
            if marker is None or diagnostic.rule != marker.failure_rule:
                unexpected.append(diagnostic)
        results.append(FeatureResult(feature, markers, unexpected))
    return results


def source_line(path: str, line: int) -> str:
    lines = (TYPECHECK_TESTS_DIR / path).read_text(encoding="utf-8").splitlines()
    return lines[line - 1].strip() if 0 < line <= len(lines) else ""


def outcome_lines(results: list[FeatureResult]) -> list[str]:
    """Everything that is not a pass, one line per (location, rule), without ty's messages: those change
    with every type-rendering tweak, while this file should only change when a result does."""
    entries = set()
    for result in results:
        for marker in result.markers:
            if not marker.passed:
                entries.add((marker.path, marker.line, marker.failure_rule, marker.source))
        for d in result.unexpected:
            entries.add((d.path, d.line, d.rule, source_line(d.path, d.line)))
    return [f"{path}:{line} {rule} | {source}" for path, line, rule, source in sorted(entries)]


def expected_file(generator: str, version: str) -> Path:
    return EXPECTED_DIR / generator / f"{version}.txt"


def read_expected(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]


def in_features(line: str, features: list[str]) -> bool:
    return any(line.startswith(f"features/{feature}/") for feature in features)


def write_expected(path: Path, generator: str, version: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        f"# Feature-test results that are not passes, {generator} stubs, Blender {version}.",
        f"# `mise run check:features {version}` fails when they change; `--update` rewrites this file.",
        "# Format: path:line rule | source line",
    ]
    path.write_text("\n".join(header + sorted(lines)) + "\n", encoding="utf-8")


def summary_markdown(results: list[FeatureResult], generator: str, version: str) -> str:
    out = [f"# Feature tests: {generator} stubs, Blender {version}", "",
           "| Feature | assert_type | expected errors | other diagnostics |", "| --- | --- | --- | --- |"]
    for r in results:
        a_pass, a_total = r.counts("assert_type")
        e_pass, e_total = r.counts("expected-error")
        out.append(f"| {r.name} | {a_pass}/{a_total} | {e_pass}/{e_total} | {len(r.unexpected)} |")
    for r in results:
        failing = [m for m in r.markers if not m.passed]
        if not failing and not r.unexpected:
            continue
        out += ["", f"## {r.name}", ""]
        for m in failing:
            messages = "; ".join(d.message for d in m.diagnostics if d.rule == m.failure_rule)
            out.append(f"- FAIL `{m.path}:{m.line}` `{m.source}`: {messages}")
        for d in r.unexpected:
            out.append(f"- {d.severity}[{d.rule}] `{d.path}:{d.line}:{d.col}`: {d.message}")
    return "\n".join(out) + "\n"


def print_table(results: list[FeatureResult]) -> None:
    width = max(len(r.name) for r in results)
    print(f"    {'feature'.ljust(width)}  assert_type  expected errors  other", flush=True)
    for r in results:
        a_pass, a_total = r.counts("assert_type")
        e_pass, e_total = r.counts("expected-error")
        print(f"    {r.name.ljust(width)}  {f'{a_pass}/{a_total}':>11}  {f'{e_pass}/{e_total}':>15}  {len(r.unexpected):>5}",
              flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_stubs_arguments(parser)
    parser.add_argument("features", nargs="*", help=f"Feature directory names in {FEATURES_DIR} (default: all)")
    parser.add_argument("--debug", action="store_true", help="Use a debug build of ty")
    parser.add_argument("--update", action="store_true", help="Rewrite the expected results instead of comparing")
    args = parser.parse_args()

    available = feature_names()
    unknown = set(args.features) - set(available)
    if unknown:
        raise StepError(f"Unknown features {', '.join(sorted(unknown))} (available: {', '.join(available)})")
    features = args.features or available

    generators = resolve_generators(args.version, args.ref, args.generator)
    all_stubs = {g: generate_stubs(args.version, generator=g, ref=args.ref, blender=args.blender, force=args.force)
                 for g in generators}
    python_version = blender_python_version(ensure_worktree(args.version, args.ref))
    ty = build_ty(args.debug)

    changed = False
    for generator, stubs in all_stubs.items():
        cmd = [ty, "check", "--project", TYPECHECK_TESTS_DIR, "--python-version", python_version,
               "--extra-search-path", stubs, "--output-format", "concise", "--no-progress",
               *(FEATURES_DIR / f for f in features)]
        log(f"Running ty (Python {python_version}, Blender {args.version}, {generator} stubs) on {len(features)} features")
        print(f"    $ {' '.join(str(c) for c in cmd)}", flush=True)
        result = subprocess.run([str(c) for c in cmd], cwd=TYPECHECK_TESTS_DIR, capture_output=True, text=True,
                                encoding="utf-8")
        if result.returncode not in (0, 1):
            raise StepError(f"ty failed with exit code {result.returncode}:\n{result.stderr}")

        results = evaluate(features, parse_diagnostics(result.stdout))
        results_dir = RESULTS_DIR / args.version / generator
        results_dir.mkdir(parents=True, exist_ok=True)
        (results_dir / "ty.txt").write_text(result.stdout, encoding="utf-8")
        (results_dir / "summary.md").write_text(summary_markdown(results, generator, args.version), encoding="utf-8")
        print_table(results)
        log(f"Summary: {results_dir / 'summary.md'}")

        path = expected_file(generator, args.version)
        actual = outcome_lines(results)
        recorded = read_expected(path)
        expected = [line for line in recorded if in_features(line, features)]
        if args.update:
            others = [line for line in recorded if not in_features(line, features)]
            write_expected(path, generator, args.version, others + actual)
            log(f"Wrote {path}")
            continue
        if not path.is_file():
            log(f"No recorded results in {path}; run with --update to record them")
            changed = True
            continue
        new = sorted(set(actual) - set(expected))
        gone = sorted(set(expected) - set(actual))
        if new or gone:
            changed = True
            log(f"Results changed against {path.relative_to(TYPECHECK_TESTS_DIR.parent.parent)} "
                f"({len(new)} new, {len(gone)} gone; --update records them):")
            for line in gone:
                print(f"    - {line}", flush=True)
            for line in new:
                print(f"    + {line}", flush=True)
        else:
            log(f"Results match {path.relative_to(TYPECHECK_TESTS_DIR.parent.parent)}")
    return 1 if changed else 0


if __name__ == "__main__":
    main_wrapper(main)
