from _baseline import (
    compare,
    merge,
    progress,
    progress_markdown,
    read_lines,
    read_sections,
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
    text = "assert_type(x, int)\nassert_type(y, str)\ny = 1  # ty: ignore[blender-x]\nfoo()\n"
    markers = parse_type_file(check, text).markers
    ide_path = "features/props/alpha/ide_alpha.py"
    ide = parse_ide_file(ide_path, 'x.a\n# ^hover-none\nx.b\n# ^hover-contains "int"\nx.c\n# ^hover\n')
    recorded = dict.fromkeys(
        [
            entry(check, ASSERT_FAILURE, "assert_type(x, int)"),
            entry(check, UNKNOWN_RULE, "y = 1  # ty: ignore[blender-x]"),
            entry(check, "unresolved-reference", "foo()"),
            entry("features/regs/legacy.py", "invalid-type-form", "x: IntProperty()"),
        ],
        "",
    )
    # ^hover only records, so it counts neither as a pass nor at all
    recorded_ide = {ide[0].title: "PASS", ide[1].title: "FAIL: does not contain", ide[2].title: "(no hover)"}
    props, regs = progress(["props", "regs"], markers, ide, recorded, recorded_ide)
    assert (props.asserts, props.expected_errors, props.ide, props.other) == ([1, 2], [0, 1], [1, 2], 1)
    assert (regs.asserts, regs.other) == ([0, 0], 1)
    table = progress_markdown("t", [props, regs], with_ide=True)
    assert "| props | 1/2 | 0/1 | 1/2 | 1 |" in table
    assert "| regs | - | - | - | 1 |" in table
    assert "| **total** | 1/2 | 0/1 | 1/2 | 2 |" in table


def test_progress_without_ide_results():
    ide = parse_ide_file("features/props/alpha/ide_alpha.py", "x.a\n# ^hover-none\n")
    [props] = progress(["props"], [], ide, {}, None)
    assert props.ide == [0, 1]
    assert "not recorded" in progress_markdown("t", [props], with_ide=False)
