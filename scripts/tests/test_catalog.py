from pathlib import Path
from textwrap import dedent

import pytest

from _catalog import (
    PAGES_DIR,
    Catalog,
    Recorded,
    Topics,
    catalog_problems,
    checked_entries,
    code_hash,
    differences,
    differs_problems,
    first_sentence,
    make_entry,
    pages,
    parse_header,
    read_recorded,
    read_topics,
    render_entry,
    shown_code,
    split_header,
    verdict,
)
from _common import CATALOG_DIR, catalog_entries
from _features import Addon, catalog_entry_list
from examples_coverage import RULES_MD

PATH = "properties/sample.py"

HANDLED = """\
    # /// catalog
    # title = "A sample"
    # section = "declaring"
    # status = "handled"
    # handled-by = ["typechecker"]
    # ///
    \"\"\"The prose. Its second sentence.\"\"\"

    # catalog: hide
    from typing import assert_type

    # catalog: show
    from bpy.props import IntProperty
    from bpy.types import PropertyGroup


    class Settings(PropertyGroup):
        count: IntProperty()


    # catalog: hide
    def _(settings: Settings) -> None:
        # catalog: show
        assert_type(settings.count, int)
        settings.count = "two"  # ty: ignore[invalid-assignment]
"""

GAPPED = """\
    # /// catalog
    # title = "A gap"
    # section = "value-types"
    # status = "not-handled"
    # [future]
    # class = "planned"
    # note = "Read the unpacked tuple."
    # tracked = "later/enum-items-unpacked"
    # ///
    \"\"\"Unpacked items are not read.\"\"\"

    from typing import Literal, assert_type

    from bpy.props import EnumProperty
    from bpy.types import PropertyGroup

    OTHERS = (("B", "B", ""),)


    class Settings(PropertyGroup):
        mode: EnumProperty(items=(("A", "A", ""), *OTHERS))


    def _(settings: Settings) -> None:
        # gap: the unpacked values are not read
        assert_type(settings.mode, Literal["A", "B"])
"""


def entry(text: str, path: str = PATH, **files: str):
    topic, _, name = path.partition("/")
    texts = {path: dedent(text), **{f"{topic}/{k}": dedent(v) for k, v in files.items()}}
    return make_entry(topic, Path(name).stem, path, texts)


def header(text: str):
    return parse_header(PATH, dedent(text).splitlines())


def recorded(entry_, results=(), hash_="abc"):
    return Recorded({entry_.rel: hash_}, {(entry_.main, rule, key) for rule, key in results})


GAP_RESULT = ("type-assertion-failure", 'assert_type(settings.mode, Literal["A", "B"])')


# --- the header ---------------------------------------------------------------------------------------------------------


def test_header_block_is_split_from_the_code():
    lines, code = split_header("a = 1\n# /// catalog\n# title = 'x'\n# ///\nb = 2\n")
    assert lines == ["# title = 'x'"]
    assert code == ["a = 1", "b = 2"]


def test_no_header_block():
    assert split_header("a = 1\n") == ([], ["a = 1"])


def test_a_handled_entry_parses_without_problems():
    made = entry(HANDLED)
    assert made.problems == []
    assert made.header.handled_by == ("typechecker",)
    assert made.id == "properties/sample"
    assert made.prose == "The prose. Its second sentence."


@pytest.mark.parametrize(
    ("lines", "problem"),
    [
        ('title = "t"\nsection = "s"\nstatus = "handled"', "names its `handled-by`"),
        ('title = "t"\nsection = "s"\nstatus = "partial"\nhandled-by = ["typechecker"]', "says in `note`"),
        ('title = "t"\nsection = "s"\nstatus = "not-handled"', "needs a [future] table"),
        ('title = "t"\nsection = "s"\nstatus = "not-handled"\n[future]\nclass = "planned"\nnote = "n"', "`tracked`"),
        ('title = "t"\nsection = "s"\nstatus = "not-handled"\n[future]\nclass = "maybe"\nnote = "n"', "class `maybe`"),
        ('title = "t"\nsection = "s"\nstatus = "done"', "status `done`"),
        ('title = "t"\nsection = "s"\nstatus = "unknown"\ncolour = "red"', "unknown header key `colour`"),
        ('title = "t"\nstatus = "unknown"', "needs `section`"),
        ('title = "t"\nsection = "s"\nstatus = "handled"\nhandled-by = ["mypy"]', "`mypy` is no handler"),
        ('title = "t"\nsection = "s"\nstatus = "handled"\nhandled-by = ["blender-runtime"]', "needs `evidence`"),
        ('title = "t"\nsection = "s"\nstatus = "unknown"\nhandled-by = ["typechecker"]', "has no `handled-by`"),
        ('title = "t"\nsection = "s"\nstatus = "unknown"\n[differs]\n"mypy/1" = "x"', "no other recorded"),
        ('title = "t"\nsection = "s"\nstatus = "handled"\nhandled-by = ["typechecker"]\n[future]\nclass = "possible"\nnote = "n"', "only a not-handled or partial"),
    ],
)
def test_header_rules(lines, problem):
    _, problems = header("\n".join(f"# {line}" for line in lines.splitlines()))
    assert any(problem in p for p in problems), problems


def test_an_invalid_header_is_one_problem():
    _, problems = header("# title = \n")
    assert len(problems) == 1 and "no valid TOML" in problems[0]


def test_entry_needs_a_header_and_prose():
    made = entry("x = 1\n")
    assert any("no `# /// catalog` header" in p for p in made.problems)
    assert any("module docstring" in p for p in made.problems)


def test_only_the_main_file_has_a_header():
    made = entry(HANDLED, "addons/kit/__init__.py", **{"kit/other.py": "# /// catalog\n# title = 'x'\n# ///\n"})
    assert any("only the entry's main file" in p for p in made.problems)


def test_a_gap_needs_a_reason():
    made = entry(HANDLED.replace("        assert_type(settings", "        # gap:\n        assert_type(settings"))
    assert any("needs a reason" in p for p in made.problems)


def test_first_sentence():
    assert first_sentence("One `a.b` thing.\nAnother one.") == "One `a.b` thing."
    assert first_sentence("No full stop") == "No full stop"


# --- the code on the page -----------------------------------------------------------------------------------------------


def test_shown_code_hides_and_dedents_the_wrapper():
    assert shown_code(dedent(HANDLED)) == dedent("""\
        from bpy.props import IntProperty
        from bpy.types import PropertyGroup


        class Settings(PropertyGroup):
            count: IntProperty()


        assert_type(settings.count, int)
        settings.count = "two"  # reported: invalid-assignment""")


def test_a_hidden_line_inside_a_shown_function_keeps_the_indentation():
    text = """\
        \"\"\"Doc.\"\"\"
        def bump(scene):
            # catalog: hide
            assert_type(scene.counter, int)
            # catalog: show
            scene.counter += 1
    """
    assert shown_code(dedent(text)) == "def bump(scene):\n    scene.counter += 1"


def test_a_gap_reads_as_not_handled_yet():
    code = shown_code(dedent(GAPPED))
    assert "    # not handled yet: the unpacked values are not read" in code
    assert "Unpacked items" not in code  # the docstring


# --- recorded results ---------------------------------------------------------------------------------------------------


def test_checked_lines_come_before_each_entrys_results(tmp_path):
    a = tmp_path / "topic" / "a.py"
    b = tmp_path / "topic" / "b"
    a.parent.mkdir()
    a.write_text("x = 1\n", encoding="utf-8")
    b.mkdir()
    (b / "__init__.py").write_text("y = 2\n", encoding="utf-8")
    entries = [Addon("topic", a, tmp_path, a.parent), Addon("topic", b, tmp_path, b.parent)]
    results = {"topic/b/__init__.py | invalid-assignment | y = 2": "msg", "topic/a.py | unresolved-reference | x = 1": ""}
    lines = list(checked_entries(entries, results))
    assert [line.split(" | ")[:2] for line in lines] == [
        ["topic/a.py", "checked"],
        ["topic/a.py", "unresolved-reference"],
        ["topic/b", "checked"],
        ["topic/b/__init__.py", "invalid-assignment"],
    ]


def test_the_hash_ignores_the_header_and_line_endings(tmp_path):
    path = tmp_path / "t" / "a.py"
    path.parent.mkdir()
    addon = Addon("t", path, tmp_path, path.parent)
    path.write_text("# /// catalog\n# status = 'handled'\n# ///\nx = 1\n", encoding="utf-8")
    first = code_hash(addon)
    path.write_bytes(b"# /// catalog\r\n# status = 'partial'\r\n# ///\r\nx = 1\r\n")
    assert code_hash(addon) == first
    path.write_text("x = 2\n", encoding="utf-8")
    assert code_hash(addon) != first


def test_read_recorded(tmp_path):
    path = tmp_path / "main.catalog.txt"
    path.write_text("# header\nt/a.py | checked | abc\nt/a.py | type-assertion-failure | assert_type(a | b, c)\n")
    got = read_recorded(path)
    assert got.hashes == {"t/a.py": "abc"}
    assert got.results == {("t/a.py", "type-assertion-failure", "assert_type(a | b, c)")}


# --- the verdict --------------------------------------------------------------------------------------------------------


def test_a_handled_entry_holds():
    made = entry(HANDLED)
    assert verdict(made, recorded(made), "abc") == []


def test_never_checked_and_changed_entries():
    made = entry(HANDLED)
    assert "never checked" in verdict(made, Recorded(), "abc")[0]
    assert "changed since it was checked" in verdict(made, recorded(made, hash_="old"), "abc")[0]


def test_a_result_outside_a_gap_is_a_surprise():
    made = entry(HANDLED)
    problems = verdict(made, recorded(made, [("type-assertion-failure", "assert_type(settings.count, int)")]), "abc")
    assert problems == [
        f"{PATH}: `type-assertion-failure` on `assert_type(settings.count, int)`, which no Gap tag marks: "
        "fix the entry or tag it"
    ]


def test_a_gap_that_fails_holds():
    made = entry(GAPPED)
    assert verdict(made, recorded(made, [GAP_RESULT]), "abc") == []


def test_a_gap_that_holds_now_fails_the_check():
    made = entry(GAPPED)
    problems = verdict(made, recorded(made), "abc")
    assert any("the gap holds now: remove the tag and review `status`" in p for p in problems)
    assert not any("shows with a Gap tag what fails today" in p for p in problems)  # it has one


def test_handled_entries_need_a_marker_and_no_gap():
    no_marker = entry(HANDLED.replace("assert_type(settings.count, int)", "settings.count").replace(
        '  # ty: ignore[invalid-assignment]', ""))
    assert any("with a marker" in p for p in verdict(no_marker, recorded(no_marker), "abc"))
    linter = entry(HANDLED.replace('["typechecker"]', '["linter-profile"]').replace(
        "assert_type(settings.count, int)", "settings.count").replace('  # ty: ignore[invalid-assignment]', ""))
    assert verdict(linter, recorded(linter), "abc") == []
    gapped = entry(GAPPED.replace('status = "not-handled"', 'status = "handled"\n    # handled-by = ["typechecker"]'))
    assert any("has no Gap tag" in p for p in verdict(gapped, recorded(gapped, [GAP_RESULT]), "abc"))


def test_partial_needs_a_holding_marker_and_a_gap():
    text = GAPPED.replace('status = "not-handled"', 'status = "partial"\n    # handled-by = ["typechecker"]\n    # note = "n"')
    only_gap = entry(text)
    assert any("a partial entry has a marker that holds" in p for p in verdict(only_gap, recorded(only_gap, [GAP_RESULT]), "abc"))
    both = entry(text.replace("        # gap:", "        assert_type(settings, Settings)\n        # gap:"))
    assert verdict(both, recorded(both, [GAP_RESULT]), "abc") == []


def test_planned_entries_need_a_gap():
    made = entry(GAPPED.replace("        # gap: the unpacked values are not read\n", "").replace(
        'assert_type(settings.mode, Literal["A", "B"])', "settings.mode"))
    assert any("a planned entry shows with a Gap tag" in p for p in verdict(made, recorded(made), "abc"))


def test_not_checkable_entries_need_nothing():
    made = entry(GAPPED.replace('class = "planned"', 'class = "not-checkable"').replace(
        "        # gap: the unpacked values are not read\n", "").replace('assert_type(settings.mode, Literal["A", "B"])', "settings.mode"))
    assert verdict(made, recorded(made), "abc") == []
    assert not made.checked


# --- differences between generators and versions -----------------------------------------------------------------------


def test_a_difference_needs_a_note():
    made = entry(HANDLED)
    other = recorded(made, [("invalid-assignment", "x")])
    found = differences(made, recorded(made), {("fake-bpy-module", "main"): other, ("builtin", "5.2"): Recorded()})
    assert found == {"fake-bpy-module/main": True}
    assert "say why in [differs]" in differs_problems(made, found, {})[0]
    assert differs_problems(made, found, {"fake-bpy-module/main": "blanket"}) == []


def test_a_note_without_a_difference_is_stale():
    made = entry(HANDLED.replace("# ///\n", '# [differs]\n    # "builtin/5.2" = "why"\n    # ///\n', 1))
    found = differences(made, recorded(made), {("builtin", "5.2"): recorded(made)})
    assert "is stale" in differs_problems(made, found, {})[0]


def test_another_result_recorded_from_older_code_is_not_compared():
    made = entry(HANDLED)
    found = differences(made, recorded(made), {("builtin", "5.2"): recorded(made, [("x", "y")], hash_="old")})
    assert found == {}


# --- pages --------------------------------------------------------------------------------------------------------------

TOPICS = """
intro = "The catalog."
[handler.typechecker]
title = "the add-on typechecker"
description = "ty-blender."
[class]
planned = "Tracked."
[topic.properties]
title = "Properties"
covers = "declaring"
intro = "Properties."
[[topic.properties.sections]]
id = "declaring"
title = "Declaring"
[[topic.properties.sections]]
id = "value-types"
title = "Value types"
to-come = ["vectors"]
"""


def test_topics_name_every_handler_and_class():
    topics = read_topics(TOPICS)
    assert "topics.toml: no [handler.stub-generator]" in topics.problems
    assert "topics.toml: no [class.possible]" in topics.problems
    assert [s.id for s in topics.topic("properties").sections] == ["declaring", "value-types"]


def test_rendered_entries():
    topics = read_topics(TOPICS)
    levels = {"invalid-assignment": "error", "type-assertion-failure": "error"}
    handled = "\n".join(render_entry(entry(HANDLED), topics, Recorded(), levels, {}))
    assert '<a id="sample"></a>\n### A sample' in handled
    assert "**Handled** by [the add-on typechecker](by-handler.md#typechecker)" in handled
    assert "**What you see:** `settings.count` is `int`; ty reports [`invalid-assignment`](" in handled
    assert "(error) on the line marked *reported*." in handled
    assert "[source](../../examples/catalog/properties/sample.py)" in handled
    gapped = entry(GAPPED)
    text = "\n".join(render_entry(gapped, topics, recorded(gapped, [GAP_RESULT]), levels, {"builtin/5.2": True}))
    assert "**Not handled** (planned) · checked with Blender main" in text
    assert "on the line marked *not handled yet*" in text
    assert "**Future:** Planned: Read the unpacked tuple. (tracked: `later/enum-items-unpacked`)" in text


def test_pages_list_every_entry_and_what_is_to_come():
    topics = read_topics(TOPICS)
    made = [entry(HANDLED), entry(GAPPED, "properties/gap.py")]
    files = pages(Catalog(topics, made, Recorded(), {}, {}))
    assert set(files) == {"README.md", "by-handler.md", "roadmap.md", "properties.md"}
    assert "- [A sample](properties.md#sample) (handled): The prose." in files["README.md"]
    assert "| [Properties](properties.md) | declaring | 1 |  | 1 |  | 1 |" in files["README.md"]
    assert "To come in this section: vectors." in files["properties.md"]
    assert "- [A gap](properties.md#gap) (not handled): Unpacked items are not read. *Read the unpacked tuple.*" in files["roadmap.md"]
    assert "- [A sample](properties.md#sample)" in files["by-handler.md"]


def test_stems_are_unique_and_shadow_no_module():
    topics = Topics()
    clash = [entry(HANDLED), entry(HANDLED, "addons/sample.py"), entry(HANDLED, "addons/enum.py")]
    problems = catalog_problems(Catalog(topics, clash, Recorded(), {}, {}))
    assert any("stems are unique" in p for p in problems)
    assert any("`enum` is also a module name" in p for p in problems)


def test_entries_are_selected_by_topic_and_id():
    assert catalog_entries(["properties/annotated-property"]) == [CATALOG_DIR / "properties" / "annotated_property.py"]
    assert all(p.parent.name == "properties" for p in catalog_entries(["properties"]))
    with pytest.raises(Exception, match="Unknown catalog topic or entry"):
        catalog_entries(["nothing"])


def test_catalog_entries_are_addons_of_their_topic():
    (first,) = catalog_entry_list(["properties/annotated-property"])
    assert (first.feature, first.rel, first.name) == ("properties", "properties/annotated_property.py", "annotated_property.py")


@pytest.mark.skipif(not RULES_MD.is_file(), reason="the ruff-blender submodule is not checked out")
def test_the_catalog_holds_and_its_pages_are_current():
    """What ``mise run catalog:generate --check`` checks, on the repository as it is."""
    from generate_catalog import TY_TOML, current

    catalog, problems, ty_toml = current()
    assert problems == []
    for name, text in pages(catalog).items():
        assert (PAGES_DIR / name).read_text(encoding="utf-8") == text, f"run `mise run catalog:generate` ({name})"
    assert TY_TOML.read_text(encoding="utf-8") == ty_toml
