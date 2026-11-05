"""How ty's diagnostics become marker results: the failure modes of every marker kind, through ``evaluate_addon``.

The scenario is one add-on with a check file and an ``__init__.py``, and the concise output a ty run could give.
"""

from textwrap import dedent

from _baseline import type_entries
from _common import TYPECHECK_TESTS_DIR
from _features import Addon, AddonResult, Diagnostic, evaluate_addon, parse_diagnostics
from _markers import ASSERT_FAILURE, UNKNOWN_RULE, UNUSED_IGNORE, parse_type_file

ROOT = "features/f/addon"
CHECK = f"{ROOT}/check_addon.py"
INIT = f"{ROOT}/__init__.py"
ADDON = Addon("f", TYPECHECK_TESTS_DIR / ROOT)

CHECK_TEXT = dedent(
    """\
    assert_type(s.ok, int)
    assert_type(s.wrong, int)
    s.x = "a"  # ty: ignore[invalid-assignment]
    s.y = "a"  # ty: ignore[invalid-assignment]
    del s.z  # ty: ignore[blender-a]
    del s.w  # ty: ignore[blender-a]
    assert_type(v, bpy_prop_array[float])
    foo()
    assert_type(__package__, str)  # oracle-skip: stock ty says str | None
    """
)
INIT_TEXT = 'count: IntProperty()  # ty: ignore[blender-legacy-property]\nx: int = "a"\n'

TY_OUTPUT = dedent(
    f"""\
    {CHECK}:2:5: error[{ASSERT_FAILURE}] Type `str` does not match asserted type `int`
    {CHECK}:4:20: error[{UNUSED_IGNORE}] Unused `ty: ignore` directive
    {CHECK}:5:20: warning[{UNKNOWN_RULE}] Unknown rule `blender-a`
    {CHECK}:7:16: error[not-subscriptable] Cannot subscript object of type `<class 'bpy_prop_array'>`
    {CHECK}:8:1: error[unresolved-reference] Name `foo` used when not defined
    {CHECK}:9:5: error[{ASSERT_FAILURE}] Type `str | None` does not match asserted type `str`
    {INIT}:1:30: warning[{UNKNOWN_RULE}] Unknown rule `blender-legacy-property`
    {INIT}:2:10: error[invalid-assignment] Object of type `Literal["a"]` is not assignable to `int`
    {ROOT}/ide_addon.py:3:1: error[unresolved-attribute] Object of type `Scene` has no attribute `reg_`
    {ROOT}/_expected/addon/__init__.pyi:1:1: error[invalid-syntax] from a reference stub
    features/f/other/check_other.py:1:1: error[unresolved-reference] another addon's
    Found 11 diagnostics
    """
)


def evaluated(output: str = TY_OUTPUT) -> AddonResult:
    files = {CHECK: parse_type_file(CHECK, CHECK_TEXT), INIT: parse_type_file(INIT, INIT_TEXT)}
    return evaluate_addon(ADDON, files, parse_diagnostics(output))


def passed(result: AddonResult) -> dict[tuple[str, int], bool]:
    return {(m.marker.path, m.marker.line): m.passed for m in result.markers}


def test_parse_diagnostics_reads_the_concise_format():
    [first, *_] = parse_diagnostics(TY_OUTPUT)
    assert first == Diagnostic(CHECK, 2, 5, "error", ASSERT_FAILURE, "Type `str` does not match asserted type `int`")
    assert len(parse_diagnostics(TY_OUTPUT)) == 11  # the summary line is not a diagnostic


def test_parse_diagnostics_makes_absolute_paths_relative_to_the_base(tmp_path):
    output = f"{tmp_path / 'features' / 'x.py'}:1:2: error[rule] message\n"
    [diagnostic] = parse_diagnostics(output, base=tmp_path)
    assert diagnostic.path == "features/x.py"


def test_every_failure_mode_of_a_marker():
    assert passed(evaluated()) == {
        (CHECK, 1): True,  # nothing reported
        (CHECK, 2): False,  # wrong type: type-assertion-failure
        (CHECK, 3): True,  # the expected error was reported (and suppressed by the comment)
        (CHECK, 4): False,  # the expected error is gone: unused-ignore-comment
        (CHECK, 5): False,  # a blender-* rule ty does not have yet: ignore-comment-unknown-rule
        (CHECK, 6): True,  # a blender-* rule ty-blender reports
        (CHECK, 7): False,  # the asserted type does not resolve, so ty compares Unknown with Unknown
        (CHECK, 9): False,
        (INIT, 1): False,  # markers in the add-on's own modules count too
    }


def test_a_markers_own_failure_is_not_unexpected_but_any_other_diagnostic_is():
    result = evaluated()
    by_line = {(m.marker.path, m.marker.line): m for m in result.markers}
    assert [d.rule for d in by_line[(CHECK, 2)].failures] == [ASSERT_FAILURE]
    assert by_line[(CHECK, 7)].failures == []  # not its own rule, yet it fails the marker
    assert [(d.path, d.line, d.rule) for d in result.unexpected] == [
        (CHECK, 7, "not-subscriptable"),
        (CHECK, 8, "unresolved-reference"),
        (INIT, 2, "invalid-assignment"),
    ]


def test_ide_files_reference_stubs_and_other_addons_are_left_out():
    paths = {d.path for m in evaluated().markers for d in m.diagnostics} | {d.path for d in evaluated().unexpected}
    assert paths == {CHECK, INIT}


def test_counts_per_marker_kind():
    result = evaluated()
    assert result.counts("assert_type") == (1, 4)
    assert result.counts("expected-error") == (2, 5)


def test_nothing_reported_passes_everything():
    result = evaluated(output="All checks passed!\n")
    assert all(passed(result).values())
    assert result.unexpected == []


def test_entries_record_each_failing_line_once_per_rule_by_line_text():
    assert list(type_entries([evaluated()])) == [
        f"{INIT} | {UNKNOWN_RULE} | count: IntProperty()  # ty: ignore[blender-legacy-property]",
        f'{INIT} | invalid-assignment | x: int = "a"',
        f"{CHECK} | {ASSERT_FAILURE} | assert_type(s.wrong, int)",
        f'{CHECK} | {UNUSED_IGNORE} | s.y = "a"  # ty: ignore[invalid-assignment]',
        f"{CHECK} | {UNKNOWN_RULE} | del s.z  # ty: ignore[blender-a]",
        f"{CHECK} | not-subscriptable | assert_type(v, bpy_prop_array[float])",
        f"{CHECK} | unresolved-reference | foo()",
        f"{CHECK} | {ASSERT_FAILURE} | assert_type(__package__, str)  # oracle-skip: stock ty says str | None",
    ]
