from textwrap import dedent

import pytest

from _common import StepError
from examples_coverage import (
    README,
    RULES_MD,
    TABLES_BEGIN,
    TABLES_END,
    Config,
    coverage,
    current,
    file_demos,
    read_rules,
    tables,
    updated_readme,
)

FEATURES = ["properties"]
LEVELS = {"blender-narrowed-by-poll": "warn", "blender-invalid-idname": "error"}
EXEMPT = {"blender-invalid-idname": "Blender rejects the class"}


def demos(text: str, path: str = "addon/ops.py"):
    return file_demos(path, dedent(text))


def problems(text: str, results=(), *, later=None, exempt=None):
    """The problems of one file with these recorded results, when the feature and the warn rule have a tag."""
    covered = """
        # demo: properties
        count = 1
        # demo: blender-narrowed-by-poll
        ob = context.object  # ty: ignore[blender-narrowed-by-poll]
    """
    config = Config(later or {}, EXEMPT if exempt is None else exempt)
    found = demos(covered, "addon/covered.py") + demos(text)
    return coverage(found, FEATURES, LEVELS, config, set(results)).problems


def test_a_tag_names_the_statement_below_it():
    [demo] = demos(
        """
        x = 1
        # demo: properties
        # a comment between the tag and the statement

        count = settings.count
        other = 2
        """
    )
    assert (demo.id, demo.path, demo.line) == ("properties", "addon/ops.py", 3)
    assert demo.keys == ("count = settings.count",)


def test_a_statement_over_several_lines_is_covered_whole():
    [demo] = demos(
        """
        # demo: properties
        point = convert(
            context.region,
            context.space_data.region_3d,
        )
        after = 1
        """
    )
    assert demo.keys == ("point = convert(", "context.region,", "context.space_data.region_3d,", ")")


def test_a_compound_statement_is_covered_by_its_header_and_decorators():
    [demo] = demos(
        """
        # demo: properties
        @persistent
        def on_save(
            filepath,
        ):
            scene = bpy.context.scene
        """
    )
    assert demo.keys == ("@persistent", "def on_save(", "filepath,", "):")


def test_stacked_tags_name_the_same_statement():
    first, second = demos(
        """
        # demo: properties
        # demo: later/enum-items
        value = settings.kind
        """
    )
    assert (first.id, second.id) == ("properties", "later/enum-items")
    assert first.keys == second.keys == ("value = settings.kind",)


def test_a_line_that_starts_no_statement_stands_for_itself():
    [demo] = demos(
        """
        keymap = (
            # demo: properties
            ("object.run", {"type": "A"}, None),
        )
        """
    )
    assert demo.keys == ('("object.run", {"type": "A"}, None),',)


def test_the_key_of_a_repeated_line_is_numbered_as_in_the_recorded_results():
    [demo] = demos(
        """
        ob = context.object
        # demo: properties
        ob = context.object
        """
    )
    assert demo.keys == ("ob = context.object #2",)


def test_a_tag_without_a_statement_is_an_error():
    with pytest.raises(StepError, match="no statement below"):
        demos("x = 1\n# demo: properties\n")


def test_the_markers_of_the_statement_are_read():
    [demo] = demos(
        """
        # demo: blender-narrowed-by-poll
        ob.name = 1  # ty: ignore[blender-narrowed-by-poll, invalid-assignment]
        """
    )
    key = "ob.name = 1  # ty: ignore[blender-narrowed-by-poll, invalid-assignment]"
    assert demo.markers == {(key, "blender-narrowed-by-poll"), (key, "invalid-assignment")}


def test_a_covered_set_has_no_problems():
    assert problems("") == []


def test_a_rule_tag_needs_the_rule_reported_on_its_statement():
    text = """
        # demo: blender-narrowed-by-poll
        ob = context.active_object
    """
    assert problems(text) == ["addon/ops.py:2: the statement is not reported as `blender-narrowed-by-poll`"]
    recorded = ("addon/ops.py", "blender-narrowed-by-poll", "ob = context.active_object")
    assert problems(text, [recorded]) == []
    elsewhere = ("addon/ui.py", "blender-narrowed-by-poll", "ob = context.active_object")
    assert len(problems(text, [elsewhere])) == 1


def test_a_marker_that_is_no_longer_used_does_not_show_its_rule():
    key = "ob = context.object  # ty: ignore[blender-narrowed-by-poll]"
    unused = ("addon/covered.py", "unused-ignore-comment", key)
    assert problems("", [unused]) == ["addon/covered.py:4: the statement is not reported as `blender-narrowed-by-poll`"]


def test_a_feature_tag_may_carry_a_blender_finding_but_must_not_fail():
    text = """
        # demo: properties
        size = settings.size
    """
    warned = ("addon/ops.py", "blender-narrowed-by-poll", "size = settings.size")
    assert problems(text, [warned]) == []
    failed = ("addon/ops.py", "missing-attribute", "size = settings.size")
    assert problems(text, [failed]) == [
        "addon/ops.py:2: the statement fails (missing-attribute): tag it `later/...`",
    ]


def test_a_later_topic_must_be_described_and_must_still_fail():
    text = """
        # demo: later/enum-items
        assert_type(settings.kind, str)
    """
    failing = ("addon/ops.py", "type-assertion-failure", "assert_type(settings.kind, str)")
    later = {"enum-items": {"description": "The values of an enum"}}
    assert problems(text, [failing], later=later) == []
    assert problems(text, [failing]) == [
        "addon/ops.py:2: `later/enum-items` has no [later.enum-items] entry in coverage.toml",
    ]
    assert problems(text, later=later) == [
        "addon/ops.py:2: `later/enum-items` works now: tag it as the feature it belongs to",
    ]


def test_one_failing_statement_is_enough_for_a_later_topic():
    text = """
        # demo: later/enum-items
        kind = settings.kind
        # demo: later/enum-items
        assert_type(settings.kind, str)
    """
    failing = ("addon/ops.py", "type-assertion-failure", "assert_type(settings.kind, str)")
    assert problems(text, [failing], later={"enum-items": {"description": "The values of an enum"}}) == []


def test_a_later_topic_without_a_tag_says_why():
    assert problems("", later={"wheels": {"description": "Bundled wheels"}}) == [
        "[later.wheels] in coverage.toml has no `# demo: later/wheels` tag and no `untagged`",
    ]
    assert problems("", later={"wheels": {"description": "Bundled wheels", "untagged": "needs a binary"}}) == []
    text = """
        # demo: later/wheels
        import bundled
    """
    failing = ("addon/ops.py", "import-not-found", "import bundled")
    entry = {"description": "Bundled wheels", "untagged": "needs a binary"}
    assert problems(text, [failing], later={"wheels": entry}) == [
        "[later.wheels] in coverage.toml says `untagged` but has a tag",
    ]
    assert problems("", later={"wheels": {"untagged": "needs a binary"}}) == [
        "[later.wheels] in coverage.toml has no description",
    ]


def test_an_unknown_id_is_a_problem():
    text = """
        # demo: propertys
        count = 2
    """
    assert problems(text) == ["addon/ops.py:2: `propertys` is no feature, rule or `later/` topic"]


def test_every_feature_and_rule_needs_a_tag_or_an_exemption():
    assert problems("", exempt={}) == [
        "`blender-invalid-idname` has no `# demo: blender-invalid-idname` tag and no [exempt] entry in coverage.toml",
    ]
    both = {**EXEMPT, "properties": "shown elsewhere"}
    assert problems("", exempt=both) == [
        "`properties` is exempt in coverage.toml but has a tag (addon/covered.py:2)",
    ]
    assert problems("", exempt={**EXEMPT, "blender-gone": "removed"}) == [
        "[exempt] `blender-gone` in coverage.toml is no feature or rule",
    ]


def test_the_tables_list_where_each_id_is_shown():
    found = demos(
        """
        # demo: properties
        count = 1
        # demo: properties
        size = 2
        # demo: blender-narrowed-by-poll
        ob = context.object  # ty: ignore[blender-narrowed-by-poll]
        # demo: later/enum-items
        assert_type(kind, str)
        """
    )
    later = {
        "enum-items": {"description": "A value typed `str | None`", "source": "R1"},
        "wheels": {"description": "Bundled wheels", "untagged": "needs a binary"},
    }
    failing = ("addon/ops.py", "type-assertion-failure", "assert_type(kind, str)")
    result = coverage(found, FEATURES, LEVELS, Config(later, EXEMPT), {failing})
    assert result.problems == []
    text = tables(result)
    assert text.startswith(TABLES_BEGIN)
    assert text.endswith(TABLES_END)
    feature_row = (
        "| [`properties`](../../tests/typecheck/features/properties/README.md) | [addon/ops.py](addon/ops.py) |"
    )
    assert feature_row in text
    assert "| `blender-narrowed-by-poll` | warn | [addon/ops.py](addon/ops.py) |" in text
    assert "| `blender-invalid-idname` | error | feature tests only: Blender rejects the class |" in text
    assert "| `enum-items` | A value typed `str \\| None` | R1 | [addon/ops.py](addon/ops.py) |" in text
    assert "| `wheels` | Bundled wheels |  | no line shows it: needs a binary |" in text


def test_the_readme_keeps_what_is_outside_the_marker_lines():
    text = f"# Examples\n\n{TABLES_BEGIN}\nold\n{TABLES_END}\n\nAfter.\n"
    block = f"{TABLES_BEGIN}\nnew\n{TABLES_END}"
    assert updated_readme(text, block) == f"# Examples\n\n{TABLES_BEGIN}\nnew\n{TABLES_END}\n\nAfter.\n"
    with pytest.raises(StepError, match="has no"):
        updated_readme("# Examples\n", block)


def test_the_rule_reference_gives_each_rule_its_default_level(tmp_path):
    reference = tmp_path / "rules.md"
    reference.write_text(
        dedent(
            """
            ## `blender-invalid-idname`

            <small>
            Default level: <a href="x" title="This lint has a default level of 'error'."><code>error</code></a> ·
            </small>

            Default level: <code>ignore</code> in an example is not the rule's.

            ## `call-non-callable`

            Default level: <a href="x"><code>error</code></a> ·

            ## `blender-narrowed-by-poll`

            Default level: <a href="x"><code>warn</code></a> ·
            """
        ),
        encoding="utf-8",
    )
    assert read_rules(reference) == {"blender-invalid-idname": "error", "blender-narrowed-by-poll": "warn"}


@pytest.mark.skipif(not RULES_MD.is_file(), reason="the ruff-blender submodule is not checked out")
def test_the_example_addons_cover_every_feature_and_rule():
    """What ``mise run examples:coverage --check`` checks, on the repository as it is."""
    result = current()
    assert result.problems == []
    text = README.read_text(encoding="utf-8")
    assert updated_readme(text, tables(result)) == text, "run `mise run examples:coverage`"
