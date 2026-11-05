from _baseline import (
    FEATURES,
    IDE,
    Changes,
    compare,
    describe,
    merge,
    progress,
    progress_markdown,
    read_lines,
    read_sections,
    record,
    type_entry,
    write_lines,
    write_sections,
)
from _common import TYPECHECK_TESTS_DIR
from _features import Addon
from _markers import ASSERT_FAILURE, UNKNOWN_RULE, parse_ide_file, parse_type_file

ALPHA = Addon("props", TYPECHECK_TESTS_DIR / "features/props/alpha")
BETA = Addon("props", TYPECHECK_TESTS_DIR / "features/props/beta")
LEGACY = Addon("regs", TYPECHECK_TESTS_DIR / "features/regs/legacy.py")
EXISTING = [ALPHA, BETA, LEGACY]


def entry(addon_path: str, rule: str = ASSERT_FAILURE, key: str = "assert_type(x, int)") -> str:
    return type_entry(addon_path, rule, key)


A1 = entry("features/props/alpha/check_alpha.py")
A2 = entry("features/props/alpha/check_alpha.py", key="assert_type(y, str | None)")
B1 = entry("features/props/beta/check_beta.py")
L1 = entry("features/regs/legacy.py")
STALE = entry("features/props/removed/check_removed.py")


def test_compare_only_looks_at_selected_and_stale_entries():
    recorded = dict.fromkeys([A1, B1, L1, STALE], "")
    changes = compare(recorded, dict.fromkeys([A2], ""), [ALPHA], EXISTING)
    assert changes.new == [A2]
    assert changes.gone == [A1, STALE]
    assert not compare(recorded, dict.fromkeys([A1, B1, L1], ""), EXISTING, EXISTING).new


def test_single_file_addon_owns_only_its_own_path():
    recorded = dict.fromkeys([L1, entry("features/regs/legacy.py.bak")], "")
    changes = compare(recorded, {}, [LEGACY], EXISTING)
    assert changes.gone == [L1, entry("features/regs/legacy.py.bak")]  # the .bak path belongs to no addon


def test_compare_reports_changed_bodies():
    changes = compare({A1: "old"}, {A1: "new"}, [ALPHA], EXISTING)
    assert (changes.new, changes.gone, changes.changed) == ([], [], [A1])


def test_merge_keeps_others_drops_stale_and_sorts_by_file():
    recorded = dict.fromkeys([B1, A1, STALE, L1], "")
    merged = merge(recorded, dict.fromkeys([A2], ""), [ALPHA], EXISTING)
    assert list(merged) == [A2, B1, L1]


def test_merge_keeps_order_within_a_file():
    later, earlier = entry(ALPHA.rel + "/c.py", key="z"), entry(ALPHA.rel + "/c.py", key="a")
    assert list(merge({}, dict.fromkeys([later, earlier], ""), [ALPHA], EXISTING)) == [later, earlier]


def test_lines_and_sections_round_trip(tmp_path):
    lines = dict.fromkeys([A1, A2], "")
    write_lines(tmp_path / "r.txt", ["header"], lines)
    assert (tmp_path / "r.txt").read_text(encoding="utf-8").startswith("# header\n")
    assert read_lines(tmp_path / "r.txt") == lines
    sections = {"a | ^hover @1 | x": "````text\nint\n````", "b | ^hover @2 | y": "PASS"}
    write_sections(tmp_path / "r.md", ["# title", "", "intro"], sections)
    assert read_sections(tmp_path / "r.md") == sections
    assert read_lines(tmp_path / "missing.txt") == {}


def test_progress_counts_per_feature():
    check = "features/props/alpha/check_alpha.py"
    text = (
        "assert_type(x, int)\nassert_type(y, str)\ny = 1  # ty: ignore[blender-x]\nfoo()\n"
        "assert_type(p, Props)  # bare-ok: the stub type is kept\n"
        "assert_type(v, bpy_prop_array[float])\n"
    )
    markers = parse_type_file(check, text).markers
    ide_path = "features/props/alpha/ide_alpha.py"
    ide = parse_ide_file(ide_path, 'x.a\n# ^hover-none\nx.b\n# ^hover-contains "int"\nx.c\n# ^hover\n')
    recorded = dict.fromkeys(
        [
            entry(check, ASSERT_FAILURE, "assert_type(x, int)"),
            entry(check, UNKNOWN_RULE, "y = 1  # ty: ignore[blender-x]"),
            entry(check, "unresolved-reference", "foo()"),
            # the asserted type does not resolve: no type-assertion-failure, but the marker fails all the same
            entry(check, "not-subscriptable", "assert_type(v, bpy_prop_array[float])"),
            entry("features/regs/legacy.py", "invalid-type-form", "x: IntProperty()"),
        ],
        "",
    )
    # ^hover only records, so it counts neither as a pass nor at all
    recorded_ide = {ide[0].title: "PASS", ide[1].title: "FAIL: does not contain", ide[2].title: "(no hover)"}
    props, regs = progress(["props", "regs"], markers, ide, recorded, recorded_ide)
    # the guard (bare-ok) is counted on its own, not with the assert_type markers; "other" is off-marker lines only
    assert (props.asserts, props.expected_errors, props.guards) == ([1, 3], [0, 1], [1, 1])
    assert (props.ide, props.other) == ([1, 2], 1)
    assert (regs.asserts, regs.other) == ([0, 0], 1)
    table = progress_markdown("t", [props, regs], with_ide=True)
    assert "| props | 1/3 | 0/1 | 1/1 | 1/2 | 1 |" in table
    assert "| regs | - | - | - | - | 1 |" in table
    assert "| **total** | 1/3 | 0/1 | 1/1 | 1/2 | 2 |" in table


def test_progress_without_ide_results():
    ide = parse_ide_file("features/props/alpha/ide_alpha.py", "x.a\n# ^hover-none\n")
    [props] = progress(["props"], [], ide, {}, None)
    assert props.ide == [0, 1]
    assert "not recorded" in progress_markdown("t", [props], with_ide=False)


def test_describe_shows_messages_of_new_feature_entries_but_never_records_them():
    changes = Changes(new=[A2], gone=[A1])
    lines = describe(changes, {A1: ""}, {A2: "Type `int` does not match asserted type `str | None`"}, FEATURES)
    assert lines == [
        f"    - {A1}",
        f"    + {A2}",
        "        Type `int` does not match asserted type `str | None`",
    ]


def test_describe_diffs_ide_sections_and_counts_per_feature():
    changes = Changes(changed=[A1], new=[L1])
    lines = describe(changes, {A1: "PASS\nint"}, {A1: "FAIL\nint", L1: "PASS"}, IDE)
    assert lines[0] == f"    ~ {A1}"
    assert "        -PASS" in lines and "        +FAIL" in lines
    assert lines[-2:] == ["        +PASS", "    per feature: props ~1, regs +1"]


# --- record: a whole check run against the recorded files -------------------------------------------------------------


def run(tmp_path, actual: list[str] | dict[str, str], selected=EXISTING, *, update=False, kind=FEATURES) -> bool:
    entries = actual if isinstance(actual, dict) else dict.fromkeys(actual, "a message ty printed")
    return record(kind, "gen", "main", entries, selected, update=update, directory=tmp_path, existing=EXISTING)


def test_record_without_a_file_fails_and_asks_for_update(tmp_path, capsys):
    assert run(tmp_path, [A1]) is True
    assert "run with --update to record them" in capsys.readouterr().out


def test_update_writes_the_file_and_progress_then_the_same_run_matches(tmp_path, capsys):
    assert run(tmp_path, [B1, A1], update=True) is False
    lines = (tmp_path / "gen" / "main.txt").read_text(encoding="utf-8").splitlines()
    assert [line for line in lines if not line.startswith("#")] == [A1, B1]  # sorted by file
    assert "a message" not in "\n".join(lines)  # ty's messages are shown, never recorded
    assert (tmp_path / "gen" / "main.progress.md").is_file()
    assert run(tmp_path, [A1, B1]) is False
    assert "Results match" in capsys.readouterr().out


def test_a_changed_result_fails_and_is_shown(tmp_path, capsys):
    run(tmp_path, [A1, B1], update=True)
    assert run(tmp_path, [A2, B1]) is True
    out = capsys.readouterr().out
    assert f"    - {A1}" in out
    assert f"    + {A2}\n        a message ty printed" in out
    assert "1 gone, 0 changed, 1 new" in out


def test_a_partial_run_compares_and_updates_only_its_own_addons(tmp_path):
    run(tmp_path, [A1, B1, L1], update=True)
    assert run(tmp_path, [A1], selected=[ALPHA]) is False  # beta and legacy are not part of the run
    run(tmp_path, [A2], selected=[ALPHA], update=True)
    assert read_lines(tmp_path / "gen" / "main.txt") == dict.fromkeys([A2, B1, L1], "")


def test_entries_of_a_removed_addon_are_gone_in_any_run_and_dropped_by_update(tmp_path, capsys):
    write_lines(tmp_path / "gen" / "main.txt", [], dict.fromkeys([A1, STALE], ""))
    assert run(tmp_path, [A1], selected=[ALPHA]) is True
    assert f"    - {STALE}" in capsys.readouterr().out
    run(tmp_path, [A1], selected=[ALPHA], update=True)
    assert read_lines(tmp_path / "gen" / "main.txt") == {A1: ""}


def test_ide_results_compare_their_bodies(tmp_path, capsys):
    title = 'features/props/alpha/ide_alpha.py | ^hover-contains "int" @3 | s.count'
    run(tmp_path, {title: "FAIL: no hover"}, update=True, kind=IDE)
    assert run(tmp_path, {title: "FAIL: no hover"}, kind=IDE) is False
    assert run(tmp_path, {title: "PASS"}, kind=IDE) is True
    out = capsys.readouterr().out
    assert f"    ~ {title}" in out
    assert "        -FAIL: no hover" in out and "        +PASS" in out
