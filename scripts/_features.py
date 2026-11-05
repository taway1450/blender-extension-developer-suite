"""The feature tests in ``tests/typecheck/features/``: discovery, and how diagnostics are attributed to markers.

Shared by ``check_features.py``, ``check_oracle.py``, ``check_ide.py`` and ``generate_features.py``. The marker
grammar is in ``_markers.py``, the recorded results in ``_baseline.py``. See ``tests/typecheck/README.md`` for the
layout and the marker syntax.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from _common import TYPECHECK_TESTS_DIR, StepError
from _markers import (
    ASSERT,
    EXPECTED,
    IDE_PREFIX,
    IdeMarker,
    TypeFile,
    TypeMarker,
    is_ide_file,
    line_keys,
    parse_ide_file,
    parse_type_file,
)

FEATURES_DIR = TYPECHECK_TESTS_DIR / "features"
GENERATED = "generated"  # features/<feature>/generated/<addon>/: written by generate_features.py
EXPECTED_STUBS = "_expected"  # <addon>/_expected/: reference stubs for check:oracle

# ty --output-format concise: `path:line:col: severity[rule] message`
DIAGNOSTIC = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):(?P<col>\d+): (?P<severity>\w+)\[(?P<rule>[\w-]+)\] (?P<message>.*)$"
)


@dataclass(frozen=True)
class Addon:
    """One addon of a feature: a package directory, or a legacy single-file addon (a ``.py`` file)."""

    feature: str
    path: Path

    @property
    def rel(self) -> str:
        """Path relative to tests/typecheck, e.g. ``features/properties/props_hosts``."""
        return self.path.relative_to(TYPECHECK_TESTS_DIR).as_posix()

    @property
    def name(self) -> str:
        """Path relative to the feature, e.g. ``props_hosts`` or ``generated/props_float_vector``."""
        return self.path.relative_to(FEATURES_DIR / self.feature).as_posix()

    @property
    def module(self) -> str:
        """The top-level module name the addon has as an extension root."""
        return self.path.stem

    @property
    def root(self) -> Path:
        """The directory that has to be an import root so that the addon is a top-level module."""
        return self.path.parent

    def contains(self, rel_path: str) -> bool:
        return rel_path == self.rel or rel_path.startswith(f"{self.rel}/")

    def python_files(self) -> list[Path]:
        """The addon's own ``.py`` files, without the reference stubs."""
        if self.path.is_file():
            return [self.path]
        return sorted(
            p
            for p in self.path.rglob("*.py")
            if EXPECTED_STUBS not in p.relative_to(self.path).parts and "__pycache__" not in p.parts
        )

    def type_test_files(self) -> list[Path]:
        return [p for p in self.python_files() if not p.name.startswith(IDE_PREFIX)]

    def ide_test_files(self) -> list[Path]:
        return [p for p in self.python_files() if p.name.startswith(IDE_PREFIX)]

    @property
    def expected_stubs(self) -> Path | None:
        path = self.path / EXPECTED_STUBS
        return path if self.path.is_dir() and path.is_dir() else None


def feature_names() -> list[str]:
    return sorted(p.name for p in FEATURES_DIR.iterdir() if p.is_dir() and not p.name.startswith((".", "_")))


def feature_addons(feature: str) -> list[Addon]:
    base = FEATURES_DIR / feature
    addons = []
    for child in sorted(base.iterdir()):
        if child.name.startswith((".", "_")) or child.name == "__pycache__":
            continue
        if child.is_dir() and child.name == GENERATED:
            addons += [Addon(feature, p) for p in sorted(child.iterdir()) if p.is_dir() and not p.name.startswith(".")]
        elif child.is_dir():
            addons.append(Addon(feature, child))
        elif child.suffix == ".py":
            addons.append(Addon(feature, child))  # a legacy single-file addon
    return addons


def all_addons() -> list[Addon]:
    addons = [a for f in feature_names() for a in feature_addons(f)]
    seen: dict[str, Addon] = {}
    for addon in addons:
        other = seen.setdefault(addon.module, addon)
        if other is not addon:
            raise StepError(
                f"Two addons are the top-level module {addon.module!r}: {other.rel} and {addon.rel}; "
                "addon names must be unique across all features"
            )
    return addons


def import_roots(addons: list[Addon]) -> list[str]:
    """The ty ``environment.root`` entries (relative to tests/typecheck) that make every addon top-level."""
    return sorted({a.root.relative_to(TYPECHECK_TESTS_DIR).as_posix() for a in addons})


def select(names: list[str]) -> list[Addon]:
    """Addons selected by feature name (``properties``) or by addon (``properties/props_hosts``)."""
    addons = all_addons()
    if not names:
        return addons
    selected = []
    for name in names:
        matches = [a for a in addons if a.feature == name or f"{a.feature}/{a.name}" == name]
        if not matches:
            raise StepError(f"Unknown feature or addon {name!r} (features: {', '.join(feature_names())})")
        selected += [a for a in matches if a not in selected]
    return selected


# --- markers and diagnostics ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Diagnostic:
    path: str  # relative to tests/typecheck, with forward slashes
    line: int
    col: int
    severity: str
    rule: str
    message: str


@dataclass
class MarkerResult:
    """A type marker and the diagnostics ty reported on its line."""

    marker: TypeMarker
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def failures(self) -> list[Diagnostic]:
        """The diagnostics that say the marker itself failed (``TypeMarker.failure_rules``)."""
        return [d for d in self.diagnostics if d.rule in self.marker.failure_rules]

    @property
    def passed(self) -> bool:
        """Whether ty reported nothing on the line. Any other error fails the marker too: an ``assert_type`` whose
        asserted type does not resolve (``bpy_prop_array[float]`` with non-generic stubs) compares Unknown with
        Unknown and reports no ``type-assertion-failure``, though nothing was checked."""
        return not self.diagnostics


def type_files(addon: Addon) -> dict[str, TypeFile]:
    """The parsed type-test files of the addon, by path relative to tests/typecheck."""
    files = {}
    for path in addon.type_test_files():
        rel = path.relative_to(TYPECHECK_TESTS_DIR).as_posix()
        files[rel] = parse_type_file(rel, path.read_text(encoding="utf-8"))
    return files


def ide_markers(addon: Addon) -> list[IdeMarker]:
    markers = []
    for path in addon.ide_test_files():
        rel = path.relative_to(TYPECHECK_TESTS_DIR).as_posix()
        markers += parse_ide_file(rel, path.read_text(encoding="utf-8"))
    return markers


def parse_diagnostics(output: str, base: Path = TYPECHECK_TESTS_DIR) -> list[Diagnostic]:
    """ty's concise output, with paths relative to ``base`` (tests/typecheck, or an oracle copy of it)."""
    diagnostics = []
    for text in output.splitlines():
        match = DIAGNOSTIC.match(text)
        if match:
            path = Path(match["path"])
            if path.is_absolute():
                path = path.relative_to(base)
            diagnostics.append(
                Diagnostic(
                    path.as_posix(),
                    int(match["line"]),
                    int(match["col"]),
                    match["severity"],
                    match["rule"],
                    match["message"],
                )
            )
    return diagnostics


@dataclass
class AddonResult:
    addon: Addon
    markers: list[MarkerResult]
    unexpected: list[Diagnostic]
    files: dict[str, TypeFile]

    def counts(self, kind: str) -> tuple[int, int]:
        markers = [m for m in self.markers if m.marker.kind == kind]
        return sum(m.passed for m in markers), len(markers)

    def line_key(self, path: str, line: int) -> str:
        """The key of a line of one of the addon's files (see ``_markers.line_keys``)."""
        if path not in self.files:
            text = (TYPECHECK_TESTS_DIR / path).read_text(encoding="utf-8")
            self.files[path] = TypeFile([], frozenset(), line_keys(text.splitlines()))
        keys = self.files[path].keys
        return keys[line - 1] if 0 < line <= len(keys) else ""


def evaluate(addons: list[Addon], diagnostics: list[Diagnostic]) -> list[AddonResult]:
    results = []
    for addon in addons:
        files = type_files(addon)
        markers = [MarkerResult(m) for f in files.values() for m in f.markers]
        by_line = {(m.marker.path, m.marker.line): m for m in markers}
        unexpected = []
        for diagnostic in diagnostics:
            if not addon.contains(diagnostic.path):
                continue
            if is_ide_file(diagnostic.path) or EXPECTED_STUBS in diagnostic.path.split("/"):
                continue  # editor tests (check:ide) hold unfinished code on purpose
            marker = by_line.get((diagnostic.path, diagnostic.line))
            if marker is not None:
                marker.diagnostics.append(diagnostic)
            if marker is None or diagnostic.rule not in marker.marker.failure_rules:
                unexpected.append(diagnostic)
        results.append(AddonResult(addon, markers, unexpected, files))
    return results


def summary_markdown(title: str, results: list[AddonResult]) -> str:
    out = [
        f"# {title}",
        "",
        "| Feature | Addon | assert_type | expected errors | other diagnostics |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in results:
        a_pass, a_total = r.counts(ASSERT)
        e_pass, e_total = r.counts(EXPECTED)
        out.append(
            f"| {r.addon.feature} | {r.addon.name} | {a_pass}/{a_total} | {e_pass}/{e_total} | {len(r.unexpected)} |"
        )
    for r in results:
        failing = [m for m in r.markers if not m.passed]
        if not failing and not r.unexpected:
            continue
        out += ["", f"## {r.addon.feature}/{r.addon.name}", ""]
        for m in failing:
            messages = "; ".join(f"{d.message} [{d.rule}]" for d in m.diagnostics)
            out.append(f"- FAIL `{m.marker.path}:{m.marker.line}` `{m.marker.source}`: {messages}")
        for d in r.unexpected:
            out.append(f"- {d.severity}[{d.rule}] `{d.path}:{d.line}:{d.col}`: {d.message}")
    return "\n".join(out) + "\n"


def print_table(results: list[AddonResult]) -> None:
    names = [f"{r.addon.feature}/{r.addon.name}" for r in results]
    width = max(len(n) for n in names)
    print(f"    {'addon'.ljust(width)}  assert_type  expected errors  other", flush=True)
    for name, r in zip(names, results):
        a_pass, a_total = r.counts(ASSERT)
        e_pass, e_total = r.counts(EXPECTED)
        print(
            f"    {name.ljust(width)}  {f'{a_pass}/{a_total}':>11}  {f'{e_pass}/{e_total}':>15}  {len(r.unexpected):>5}",
            flush=True,
        )
