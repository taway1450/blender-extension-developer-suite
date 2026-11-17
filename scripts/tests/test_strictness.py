"""The ``[blender] strictness`` check: how markers are removed from the copy and how reported levels are compared."""

from _features import Diagnostic
from _strictness import compare, strip_blender_markers

PATH = "features/f/addon/__init__.py"


def test_strip_removes_only_blender_codes():
    text = (
        "def execute(self, context) -> set[str]:  # ty: ignore[blender-imprecise-operator-return]\n"
        "    x = 1  # ty: ignore[invalid-assignment, blender-a]  # bare-ok: kept\n"
        'bone.mode = "X"  # ty: ignore[invalid-assignment]\n'
    )
    stripped, removed = strip_blender_markers(text)
    assert stripped == (
        "def execute(self, context) -> set[str]:\n"
        "    x = 1  # ty: ignore[invalid-assignment]  # bare-ok: kept\n"
        'bone.mode = "X"  # ty: ignore[invalid-assignment]\n'
    )
    assert removed == {1: ["blender-imprecise-operator-return"], 2: ["blender-a"]}


def diagnostic(line: int, severity: str, rule: str) -> Diagnostic:
    return Diagnostic(PATH, line, 1, severity, rule, "message")


def test_compare_levels_per_marker():
    markers = {(PATH, 1): ["blender-a"], (PATH, 2): ["blender-b"], (PATH, 3): ["blender-c"]}
    expected = {"blender-a": "warn", "blender-b": "ignore", "blender-c": "error"}
    found = [diagnostic(1, "warning", "blender-a"), diagnostic(2, "warning", "blender-b")]
    mismatches = compare("default", expected, markers, found, set(expected))
    assert [(m.line, m.message) for m in mismatches] == [
        (2, "blender-b: expected ignore, got warn"),
        (3, "blender-c: expected error, got ignore"),
    ]


def test_compare_flags_a_tested_rule_without_a_marker():
    found = [diagnostic(5, "error", "blender-a"), diagnostic(6, "error", "blender-other")]
    mismatches = compare("strict", {}, {}, found, {"blender-a"})
    assert [(m.line, m.preset, m.message) for m in mismatches] == [(5, "strict", "blender-a: expected ignore, got error")]
