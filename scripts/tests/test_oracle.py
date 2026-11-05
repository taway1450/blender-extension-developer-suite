from textwrap import dedent

from _common import TYPECHECK_TESTS_DIR
from _features import Addon, AddonResult, Diagnostic, MarkerResult
from _markers import ASSERT_FAILURE, UNKNOWN_RULE, UNUSED_IGNORE, parse_type_file
from check_oracle import bare_hits

PATH = "features/f/addon/check_addon.py"
ADDON = Addon("f", TYPECHECK_TESTS_DIR / "features/f/addon")

TEXT = dedent(
    """\
    assert_type(scene.free, int)
    assert_type(scene.needs, int)
    assert_type(scene.missing, Any)
    assert_type(props, OperatorProperties)  # bare-ok: a non-literal idname keeps the stub type
    scene.x = "a"  # ty: ignore[invalid-assignment]
    scene.y = "a"  # ty: ignore[invalid-assignment]
    scene.z = "a"  # ty: ignore[blender-a, invalid-assignment]
    scene.w = "a"  # ty: ignore[blender-a, invalid-assignment]
    del scene.v  # ty: ignore[blender-a]
    assert_type(__package__, str)  # oracle-skip: stock ty says str | None
    """
)


def diagnostic(line: int, rule: str) -> Diagnostic:
    return Diagnostic(PATH, line, 1, "error", rule, "...")


def bare_result(diagnostics: dict[int, list[str]]) -> AddonResult:
    """The add-on's markers with the bare run's diagnostics, by line."""
    parsed = parse_type_file(PATH, TEXT)
    markers = [MarkerResult(m, [diagnostic(m.line, r) for r in diagnostics.get(m.line, [])]) for m in parsed.markers]
    return AddonResult(ADDON, markers, [], {PATH: parsed})


def hit_lines(result: AddonResult) -> list[int]:
    return [m.marker.line for m in bare_hits(result)]


def test_bare_hits_are_the_markers_that_hold_without_the_checker():
    result = bare_result(
        {
            2: [ASSERT_FAILURE],  # needs the checker
            3: ["unresolved-attribute"],  # the assert holds on Unknown, but the line fails
            6: [UNUSED_IGNORE],  # stock ty reports no invalid-assignment: needs the checker
            7: [UNKNOWN_RULE],  # stock ty already reports invalid-assignment
            8: [UNKNOWN_RULE, UNUSED_IGNORE],
            9: [UNKNOWN_RULE],
        }
    )
    # 1: holds; 4: guard; 5: stock ty already rejects it; 9: blender-* only; 10: oracle-skip is judged too
    assert hit_lines(result) == [1, 5, 7, 10]


def test_nothing_holds_when_every_line_fails():
    failing = {line: [ASSERT_FAILURE] for line in (1, 2, 3, 10)} | {line: [UNUSED_IGNORE] for line in (5, 6, 7, 8)}
    assert hit_lines(bare_result(failing)) == []
