"""The ``[blender] strictness`` check of ``check:features``: the level each Blender rule is reported at under each preset.

A ``# ty: ignore[...]`` marker hides the diagnostic it expects, so the level ty reports a rule at cannot be seen in the
normal run. An add-on with ``_expected/strictness.toml`` is also checked like this: its files are copied without their
``blender-*`` markers, ty runs on the copy once per preset (``--config blender.strictness="<preset>"``), and each
removed marker's rule must be reported on its line at the level the file gives for that preset (``ignore``: not at
all). A rule the file lists must not be reported on any other line. ``tests/typecheck/ty.toml`` is copied too, so its
``[[overrides]]`` apply as in the normal run.

```toml
[lenient]
blender-imprecise-operator-return = "ignore"

[strict]
blender-imprecise-operator-return = "error"
```

A line whose level differs is recorded as a ``strictness-<preset>`` entry of the line, like any other result.
"""

from __future__ import annotations

import re
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

from _features import EXPECTED_STUBS, Addon, Diagnostic

STRICTNESS_FILE = "strictness.toml"
SUPPRESSION = re.compile(r"#\s*ty:\s*ignore\[(?P<codes>[^\]]*)\]")
BLENDER_PREFIX = "blender-"
LEVELS = {"warning": "warn", "error": "error"}


def expectations(addon: Addon) -> dict[str, dict[str, str]] | None:
    """The addon's ``_expected/strictness.toml``: the level of each rule under each preset, or None without one."""
    path = addon.path / EXPECTED_STUBS / STRICTNESS_FILE
    if not addon.path.is_dir() or not path.is_file():
        return None
    return tomllib.loads(path.read_text(encoding="utf-8"))


def strip_blender_markers(text: str) -> tuple[str, dict[int, list[str]]]:
    """``text`` without the ``blender-*`` codes of its ``# ty: ignore[...]`` markers (a marker left with no code
    goes), and the removed codes by line number."""
    lines = []
    removed: dict[int, list[str]] = {}
    for number, line in enumerate(text.splitlines(keepends=True), start=1):
        match = SUPPRESSION.search(line)
        if match:
            codes = [code.strip() for code in match["codes"].split(",") if code.strip()]
            blender = [code for code in codes if code.startswith(BLENDER_PREFIX)]
            if blender:
                removed[number] = blender
                rest = [code for code in codes if not code.startswith(BLENDER_PREFIX)]
                replacement = f"# ty: ignore[{', '.join(rest)}]" if rest else ""
                ending = line[len(line.rstrip("\r\n")) :]
                line = (line[: match.start()] + replacement + line[match.end() :]).rstrip() + ending
        lines.append(line)
    return "".join(lines), removed


@dataclass(frozen=True)
class Mismatch:
    path: str
    line: int
    preset: str
    message: str


def copy_addon(addon: Addon, base: Path, destination: Path) -> dict[tuple[str, int], list[str]]:
    """Copy ``addon`` (under ``base``, tests/typecheck) to the same place under ``destination`` without its
    ``blender-*`` markers; returns the removed rules by (path relative to ``base``, line)."""
    markers: dict[tuple[str, int], list[str]] = {}
    target = destination / addon.path.relative_to(base)
    shutil.copytree(addon.path, target, ignore=shutil.ignore_patterns("__pycache__", EXPECTED_STUBS))
    for path in addon.python_files():
        rel = path.relative_to(base).as_posix()
        text, removed = strip_blender_markers(path.read_text(encoding="utf-8"))
        (destination / rel).write_text(text, encoding="utf-8")
        for line, rules in removed.items():
            markers[(rel, line)] = rules
    return markers


def compare(
    preset: str,
    expected: dict[str, str],
    markers: dict[tuple[str, int], list[str]],
    diagnostics: list[Diagnostic],
    tested: set[str],
) -> list[Mismatch]:
    """The lines where the levels ty reported under ``preset`` differ from ``expected`` (rule -> level).

    ``markers`` are the removed markers' rules by (path, line), ``tested`` the rules the add-on's file lists: one of
    them reported on a line without its marker is a mismatch too."""
    reported = {
        (d.path, d.line, d.rule): LEVELS.get(d.severity, d.severity)
        for d in diagnostics
        if d.rule.startswith(BLENDER_PREFIX)
    }
    mismatches = []
    for (path, line), rules in sorted(markers.items()):
        for rule in rules:
            want = expected.get(rule, "ignore")
            got = reported.pop((path, line, rule), "ignore")
            if want != got:
                mismatches.append(Mismatch(path, line, preset, f"{rule}: expected {want}, got {got}"))
    for (path, line, rule), got in sorted(reported.items()):
        if rule in tested:
            mismatches.append(Mismatch(path, line, preset, f"{rule}: expected ignore, got {got}"))
    return mismatches
