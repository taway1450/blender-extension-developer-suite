"""The feature tests in ``tests/typecheck/features/``: discovery, markers and how diagnostics are attributed.

Shared by ``check_features.py``, ``check_oracle.py``, ``check_ide.py`` and ``generate_features.py``.
See ``tests/typecheck/README.md`` for the layout and the marker syntax.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from _common import TYPECHECK_TESTS_DIR, StepError

FEATURES_DIR = TYPECHECK_TESTS_DIR / "features"
GENERATED = "generated"  # features/<feature>/generated/<addon>/: written by generate_features.py
EXPECTED_STUBS = "_expected"  # <addon>/_expected/: reference stubs for check:oracle
IDE_PREFIX = "ide_"  # files for check:ide, not type tests

# ty --output-format concise: `path:line:col: severity[rule] message`
DIAGNOSTIC = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):(?P<col>\d+): (?P<severity>\w+)\[(?P<rule>[\w-]+)\] (?P<message>.*)$"
)
ASSERT_MARKER = re.compile(r"\bassert_type\(")
IGNORE_MARKER = re.compile(r"#\s*ty:\s*ignore\[(?P<rules>[^\]]+)\]")
# Rules that only ty-blender reports. Until it does, ty flags their ignore comments as unknown rules.
BLENDER_RULE_PREFIX = "blender-"
UNKNOWN_RULE = "ignore-comment-unknown-rule"


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


def result_prefixes(addons: list[Addon]) -> tuple[str, ...]:
    """The prefixes of the recorded result lines (``path:line ...``) that belong to ``addons``."""
    return tuple(f"{a.rel}/" if a.path.is_dir() else f"{a.rel}:" for a in addons)


def split_recorded(recorded: list[str], selected: list[Addon]) -> tuple[list[str], list[str]]:
    """Split recorded result lines (or IDE marker titles) into the ones this run compares and the ones it keeps.

    The compared ones belong to a selected addon or to no addon that still exists: a stale line from a removed
    or renamed addon then shows up as gone, and ``--update`` drops it. The kept ones belong to unselected addons.
    """
    selected_prefixes = result_prefixes(selected)
    current_prefixes = result_prefixes(all_addons())
    compared = [r for r in recorded if r.startswith(selected_prefixes) or not r.startswith(current_prefixes)]
    kept = [r for r in recorded if not r.startswith(selected_prefixes) and r.startswith(current_prefixes)]
    return compared, kept


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
class Marker:
    path: str
    line: int
    kind: str  # "assert_type" or "expected-error"
    source: str
    rules: tuple[str, ...] = ()  # the rules of an expected error
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def failure_rules(self) -> tuple[str, ...]:
        if self.kind == "assert_type":
            return ("type-assertion-failure",)
        # A rule ty does not know yet (a blender-* rule before ty-blender reports it) is an expected error
        # that is not found either.
        return ("unused-ignore-comment", UNKNOWN_RULE)

    @property
    def failure_rule(self) -> str:
        """The rule recorded for a failure; an unknown rule counts as an unused ignore."""
        return self.failure_rules[0]

    @property
    def passed(self) -> bool:
        return not any(d.rule in self.failure_rules for d in self.diagnostics)

    @property
    def blender_only(self) -> bool:
        """An expected error that only ty-blender can report: stock ty with reference stubs cannot."""
        return self.kind == "expected-error" and all(r.startswith(BLENDER_RULE_PREFIX) for r in self.rules)


def find_markers(addon: Addon) -> list[Marker]:
    markers = []
    for path in addon.type_test_files():
        rel = path.relative_to(TYPECHECK_TESTS_DIR).as_posix()
        for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if match := IGNORE_MARKER.search(text):
                rules = tuple(r.strip() for r in match["rules"].split(","))
                markers.append(Marker(rel, number, "expected-error", text.strip(), rules))
            elif ASSERT_MARKER.search(text) and not text.lstrip().startswith(("#", "from ", "import ")):
                markers.append(Marker(rel, number, "assert_type", text.strip()))
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
    markers: list[Marker]
    unexpected: list[Diagnostic]

    def counts(self, kind: str) -> tuple[int, int]:
        markers = [m for m in self.markers if m.kind == kind]
        return sum(m.passed for m in markers), len(markers)


def evaluate(addons: list[Addon], diagnostics: list[Diagnostic]) -> list[AddonResult]:
    results = []
    for addon in addons:
        markers = find_markers(addon)
        by_line = {(m.path, m.line): m for m in markers}
        unexpected = []
        for diagnostic in diagnostics:
            if not addon.contains(diagnostic.path):
                continue
            parts = diagnostic.path.split("/")
            if parts[-1].startswith(IDE_PREFIX) or EXPECTED_STUBS in parts:
                continue  # editor tests (check:ide) hold unfinished code on purpose
            marker = by_line.get((diagnostic.path, diagnostic.line))
            if marker is not None:
                marker.diagnostics.append(diagnostic)
            if marker is None or diagnostic.rule not in marker.failure_rules:
                unexpected.append(diagnostic)
        results.append(AddonResult(addon, markers, unexpected))
    return results


def source_line(path: str, line: int) -> str:
    lines = (TYPECHECK_TESTS_DIR / path).read_text(encoding="utf-8").splitlines()
    return lines[line - 1].strip() if 0 < line <= len(lines) else ""


def summary_markdown(title: str, results: list[AddonResult]) -> str:
    out = [
        f"# {title}",
        "",
        "| Feature | Addon | assert_type | expected errors | other diagnostics |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in results:
        a_pass, a_total = r.counts("assert_type")
        e_pass, e_total = r.counts("expected-error")
        out.append(
            f"| {r.addon.feature} | {r.addon.name} | {a_pass}/{a_total} | {e_pass}/{e_total} | {len(r.unexpected)} |"
        )
    for r in results:
        failing = [m for m in r.markers if not m.passed]
        if not failing and not r.unexpected:
            continue
        out += ["", f"## {r.addon.feature}/{r.addon.name}", ""]
        for m in failing:
            messages = "; ".join(d.message for d in m.diagnostics if d.rule in m.failure_rules)
            out.append(f"- FAIL `{m.path}:{m.line}` `{m.source}`: {messages}")
        for d in r.unexpected:
            out.append(f"- {d.severity}[{d.rule}] `{d.path}:{d.line}:{d.col}`: {d.message}")
    return "\n".join(out) + "\n"


def print_table(results: list[AddonResult]) -> None:
    names = [f"{r.addon.feature}/{r.addon.name}" for r in results]
    width = max(len(n) for n in names)
    print(f"    {'addon'.ljust(width)}  assert_type  expected errors  other", flush=True)
    for name, r in zip(names, results):
        a_pass, a_total = r.counts("assert_type")
        e_pass, e_total = r.counts("expected-error")
        print(
            f"    {name.ljust(width)}  {f'{a_pass}/{a_total}':>11}  {f'{e_pass}/{e_total}':>15}  {len(r.unexpected):>5}",
            flush=True,
        )
