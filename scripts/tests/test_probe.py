"""The probe drivers' shared runner and their verdicts on what the in-Blender scripts recorded."""

import sys
from pathlib import Path

import pytest

from _common import StepError, blender_script_command
from _probe import failed_checks, probe_parser, run_probe
from probe_freestyle import failures as freestyle_failures
from probe_modifiers_new import failures as modifiers_failures
from probe_never_none import corpus, table
from probe_node_menus import changed_menus, menu_problems

# A stand-in Blender: writes the JSON its first argument after "--" names (the arguments it got), prints a line.
FAKE_BLENDER = """\
import json, sys
args = sys.argv[sys.argv.index("--") + 1 :]
print("fake blender ran")
if args[1:2] != ["fail"]:
    json.dump({"argv": sys.argv[1:]}, open(args[0], "w"))
sys.exit(1 if args[1:2] == ["fail"] else 0)
"""


@pytest.fixture
def blender(tmp_path):
    script = tmp_path / "fake_blender.py"
    script.write_text(FAKE_BLENDER)
    launcher = tmp_path / "blender"
    launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
    launcher.chmod(0o755)
    return launcher


def test_script_command_runs_the_script_in_background_factory_blender():
    cmd = blender_script_command(Path("b"), Path("s.py"), "out.json", Path("dir"), options=("--enable-autoexec",))
    assert cmd[0] == "b"
    assert {"--background", "--factory-startup", "-noaudio", "--enable-autoexec"} <= set(cmd[: cmd.index("--python")])
    assert cmd[cmd.index("--python-exit-code") + 1] == "1"
    assert cmd[cmd.index("--python") :] == ["--python", "s.py", "--", "out.json", "dir"]


@pytest.mark.skipif(sys.platform == "win32", reason="the stand-in Blender is a shell script")
def test_run_probe_returns_the_results_and_logs_the_output(blender, tmp_path):
    result = tmp_path / "result.json"
    result.write_text("stale")
    results, output = run_probe(blender, Path("probe.py"), result, "extra")
    assert results["argv"][-4:] == ["probe.py", "--", str(result), "extra"]
    assert "fake blender ran" in output
    assert (tmp_path / "blender.log").read_text() == output


@pytest.mark.skipif(sys.platform == "win32", reason="the stand-in Blender is a shell script")
def test_run_probe_fails_when_blender_fails(blender, tmp_path):
    result = tmp_path / "result.json"
    result.write_text("{}")
    with pytest.raises(StepError, match="exit code 1"):
        run_probe(blender, Path("probe.py"), result, "fail", log_path=tmp_path / "probe.log")
    assert not result.exists()
    assert "fake blender ran" in (tmp_path / "probe.log").read_text()


def test_probe_parser_takes_the_version_and_a_blender():
    args = probe_parser("doc").parse_args(["main", "--blender", "b"])
    assert (args.version, args.blender) == ("main", Path("b"))


def test_failed_checks_quote_each_error():
    results = {"a": {"ok": True, "value": 1}, "b": {"ok": False, "error": "Traceback: boom"}}
    assert failed_checks(results) == ["b failed:\nTraceback: boom"]
    assert failed_checks(results, prefix="Rigify ", verb="raised") == ["Rigify b raised:\nTraceback: boom"]


def strokes(*colors):
    return {"ok": True, "value": [list(c) for c in colors]}


def test_freestyle_passes_when_both_renders_draw_the_same_colours():
    results = {"script_first": strokes((1, 0, 0)), "script_second": strokes((1, 0, 0)), "seed": {"ok": True}}
    assert freestyle_failures(results, "Fra:1") == []


def test_freestyle_fails_on_different_colours_no_strokes_or_a_traceback():
    differ = {"script_first": strokes((1, 0, 0)), "script_second": strokes((0, 1, 0))}
    assert freestyle_failures(differ, "") == ["pyRandomColorShader(7) gave different colours in two renders"]
    empty = {"script_first": strokes(), "script_second": strokes()}
    assert freestyle_failures(empty, "") == ["the style module drew no strokes"]
    raised = {"script_first": {"ok": False, "error": "E"}, "script_second": strokes((1, 0, 0))}
    assert freestyle_failures(raised, "Traceback (most recent call last)") == [
        "script_first raised:\nE",
        "a style module raised (see blender.log)",
    ]


def test_modifiers_probe_fails_on_a_failed_check_or_a_traceback():
    results = {"adds": {"ok": True, "value": {}}, "skipped": {"ok": True, "skipped": "no fluid"}}
    assert modifiers_failures(results, "") == []
    assert modifiers_failures({**results, "x": {"ok": False, "error": "E"}}, "") == ["x failed:\nE"]
    assert modifiers_failures(results, "Traceback") == ["Blender printed a traceback (see blender.log)"]


def draw(*entries, poll=True):
    return {"ok": True, "poll": poll, "entries": list(entries)} if poll else {"ok": True, "poll": False}


def test_changed_menus_lists_draws_that_differ_appear_or_disappear():
    previous = {"m:A [x]": draw("op1"), "m:B": draw("op2"), "m:C": draw("op3")}
    current = {"m:A [x]": draw("op1"), "m:B": draw("op2", "op4"), "m:D": draw()}
    assert changed_menus(previous, current) == ["m:B", "m:C", "m:D"]


def test_a_menu_drawn_in_some_variant_is_fine():
    results = {"m:A [engine=CYCLES]": draw(poll=False), "m:A [engine=EEVEE]": draw("op"), "m:B": draw("op")}
    assert menu_problems(results) == []


def test_a_menu_whose_poll_rejects_every_variant_or_whose_draw_raises_is_a_problem():
    results = {
        "m:A [engine=CYCLES]": draw(poll=False),
        "m:A [engine=EEVEE]": draw(poll=False),
        "m:B": {"ok": False, "error": "E"},
    }
    assert menu_problems(results) == [
        "m:B failed:\nE",
        "m:A is drawn in no variant (its poll rejects them all)",
        "m:B is drawn in no variant (its poll rejects them all)",
    ]


def test_corpus_takes_the_sorted_blend_files_but_not_the_invalid_or_tiny_ones(tmp_path):
    files = tmp_path / "tests" / "files"
    for name, size in [("b/two.blend", 2000), ("a/one.blend", 2000), ("tiny.blend", 10), ("x.txt", 2000)]:
        (files / name).parent.mkdir(parents=True, exist_ok=True)
        (files / name).write_bytes(b"\0" * size)
    (files / "invalid_blendfiles").mkdir()
    (files / "invalid_blendfiles" / "bad.blend").write_bytes(b"\0" * 2000)
    assert corpus(tmp_path, None) == [str(files / "a/one.blend"), str(files / "b/two.blend")]
    assert corpus(tmp_path, 1) == [str(files / "a/one.blend")]


def test_table_counts_synthetic_states_and_sums_the_corpus_per_member():
    synthetic = [{"member": "Scene.camera", "state": "new scene", "none": 1, "total": 1, "note": "a|b"}]
    files = [
        {"file": "/t/one.blend", "records": [rec("Scene.camera", "loaded file (saved by 2.79)", 1, 1)]},
        {"file": "/t/two.blend", "records": [rec("Scene.camera", "loaded file (saved by 4.2)", 0, 2)]},
    ]
    assert table(synthetic, files).splitlines() == [
        "| Member | State | None | Reads | Note | Files with None |",
        "|---|---|---|---|---|---|",
        "| `Scene.camera` | new scene | 1 | 1 | a\\|b |  |",
        "| `Scene.camera` | corpus files | 1 | 3 |  | one.blend |",
    ]


def rec(member, state, none, total):
    return {"member": member, "state": state, "none": none, "total": total, "note": ""}

