from _baseline import type_entries
from _common import TYPECHECK_TESTS_DIR
from _features import Addon, AddonResult, Diagnostic, MarkerResult
from _markers import ASSERT_FAILURE, parse_type_file

PATH = "features/f/addon/check_addon.py"
ADDON = Addon("f", TYPECHECK_TESTS_DIR / "features/f/addon")
TEXT = "assert_type(v, bpy_prop_array[float])\nassert_type(x, int)\nassert_type(y, int)\n"


def diagnostic(line: int, rule: str) -> Diagnostic:
    return Diagnostic(PATH, line, 1, "error", rule, rule)


def results() -> AddonResult:
    """Line 1 does not resolve its asserted type, line 2 fails its assertion, line 3 passes."""
    parsed = parse_type_file(PATH, TEXT)
    broken = diagnostic(1, "not-subscriptable")
    failed = diagnostic(2, ASSERT_FAILURE)
    markers = [MarkerResult(parsed.markers[0], [broken]), MarkerResult(parsed.markers[1], [failed])]
    markers.append(MarkerResult(parsed.markers[2]))
    # evaluate puts diagnostics that are not a marker's own failure in unexpected, on marker lines too
    return AddonResult(ADDON, markers, [broken], {PATH: parsed})


def test_any_error_on_the_line_fails_the_marker():
    broken, failed, clean = results().markers
    assert not broken.passed and broken.failures == []
    assert not failed.passed and [d.rule for d in failed.failures] == [ASSERT_FAILURE]
    assert clean.passed


def test_entries_record_each_rule_once():
    assert list(type_entries([results()])) == [
        f"{PATH} | not-subscriptable | assert_type(v, bpy_prop_array[float])",
        f"{PATH} | {ASSERT_FAILURE} | assert_type(x, int)",
    ]
