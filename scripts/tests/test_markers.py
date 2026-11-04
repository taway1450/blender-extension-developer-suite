from textwrap import dedent

import pytest
from _markers import (
    ASSERT,
    EXPECTED,
    UNKNOWN_RULE,
    UNUSED_IGNORE,
    MarkerError,
    is_check_file,
    is_ide_file,
    line_keys,
    parse_ide_file,
    parse_type_file,
)

PATH = "features/f/addon/check_addon.py"


def test_line_keys_number_repeated_text():
    assert line_keys(["  a", "b", "a  ", "", "a", ""]) == ["a", "b", "a #2", "", "a #3", " #2"]


def test_line_key_survives_lines_added_above():
    before = line_keys(["x = 1", "assert_type(x, int)"])
    after = line_keys(["# new comment", "y = 2", "x = 1", "assert_type(x, int)"])
    assert before[1] == after[3]


def test_type_markers():
    text = dedent(
        """\
        from typing import assert_type
        def _(scene: Scene) -> None:
            assert_type(scene.count, int)
            # assert_type(commented, out)
            scene.count = "x"  # ty: ignore[invalid-assignment]
            del scene.count  # ty: ignore[blender-a, blender-b]
            assert_type(__package__, str)  # oracle-skip: stock ty says str | None
            assert_type(scene.count, int)
        """
    )
    parsed = parse_type_file(PATH, text)
    assert [(m.line, m.kind, m.key) for m in parsed.markers] == [
        (3, ASSERT, "assert_type(scene.count, int)"),
        (5, EXPECTED, 'scene.count = "x"  # ty: ignore[invalid-assignment]'),
        (6, EXPECTED, "del scene.count  # ty: ignore[blender-a, blender-b]"),
        (7, ASSERT, "assert_type(__package__, str)  # oracle-skip: stock ty says str | None"),
        (8, ASSERT, "assert_type(scene.count, int) #2"),
    ]
    assert parsed.markers[2].rules == ("blender-a", "blender-b")
    assert parsed.markers[2].blender_only
    assert not parsed.markers[1].blender_only
    assert [m.oracle_skip for m in parsed.markers] == [False, False, False, True, False]
    assert parsed.oracle_skip_lines == {7}
    assert parsed.markers[0].in_check_file


def test_ignore_comment_wins_over_assert_type():
    [marker] = parse_type_file(PATH, "assert_type(x, int)  # ty: ignore[blender-x]\n").markers
    assert marker.kind == EXPECTED
    assert marker.failure_rules == (UNUSED_IGNORE, UNKNOWN_RULE)


def test_oracle_skip_without_marker():
    parsed = parse_type_file(PATH, "x: IntProperty()  # oracle-skip: the annotation itself\n")
    assert parsed.markers == []
    assert parsed.oracle_skip_lines == {1}


def test_file_kinds():
    assert is_check_file("features/f/a/check_a.py")
    assert not is_check_file("features/f/check_dir/__init__.py")
    assert is_ide_file("features/f/a/ide_a.py")
    assert not is_ide_file("features/f/a/check_ide.py")


IDE = "features/f/addon/ide_addon.py"


def test_ide_markers_query_the_code_line_above():
    text = dedent(
        """\
        def _(scene):
            scene.reg_int
            #     ^hover
            #     ^hover-contains "int"

            # a comment between
            bpy.ops.my.run(
            #             ^signature
        """
    )
    markers = parse_ide_file(IDE, text)
    assert [(m.line, m.character, m.kind, m.arg, m.source) for m in markers] == [
        (1, 10, "hover", None, "scene.reg_int"),
        (1, 10, "hover-contains", '"int"', "scene.reg_int"),
        (6, 18, "signature", None, "bpy.ops.my.run("),
    ]
    assert markers[1].title == f'{IDE} | ^hover-contains "int" @11 | scene.reg_int'
    assert markers[1].quoted_arg() == "int"


def test_ide_title_has_no_line_number_but_repeated_lines_differ():
    text = "x.a\n# ^hover\nx.a\n# ^hover\n"
    first, second = parse_ide_file(IDE, text)
    assert first.title != second.title
    assert second.title.endswith("| x.a #2")


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("x\n# ^bogus\n", r"unknown marker \^bogus"),
        ("# ^hover\n", "marker without a code line above it"),
        ("x = 'é'\n# ^hover\n", "must be ASCII"),
        ("x\n# ^hover\n# ^hover\n", "same title"),
    ],
)
def test_ide_errors(text, message):
    with pytest.raises(MarkerError, match=message):
        parse_ide_file(IDE, text)


def test_quoted_arg_requires_quotes():
    [marker] = parse_ide_file(IDE, "x\n# ^hover-contains int\n")
    with pytest.raises(MarkerError, match="quoted string"):
        marker.quoted_arg()
