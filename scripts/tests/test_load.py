"""check:load's verdict on the runtime probes of _expected/runtime.toml."""

import pytest

from check_load import probe_problems

PROBES = [
    {"code": "healthy(addon.A)", "expect": False, "reason": "detached"},
    {"code": "addon.value()", "expect": "raises"},
    {"code": "len(bpy.data.objects)", "expect": 0},
]


def test_probes_that_give_the_expected_value_hold():
    assert probe_problems(PROBES, [False, "raises RuntimeError: no", 0]) == []


def test_a_probe_with_another_value_is_a_problem():
    [problem] = probe_problems(PROBES, [True, "raises RuntimeError: no", 0])
    assert problem == "probe healthy(addon.A) gave True, expected False (detached)"


def test_raises_expects_an_exception_and_nothing_else():
    assert probe_problems(PROBES[1:2], ["raises ValueError: x"]) == []
    [problem] = probe_problems(PROBES[1:2], [None])
    assert "gave None, expected 'raises'" in problem


@pytest.mark.parametrize(
    ("expect", "got"),
    [(False, 0), (True, 1), (0, False), (1, True), ("False", False)],
)
def test_a_bool_only_matches_a_bool(expect, got):
    assert probe_problems([{"code": "x", "expect": expect}], [got]) != []


def test_numbers_match_by_value():
    assert probe_problems([{"code": "x", "expect": 2}], [2.0]) == []


def test_an_addon_that_failed_to_register_has_no_probe_results():
    """Probes run after register(); check:load reports the failed registration itself."""
    assert probe_problems(PROBES, []) == []
