from pathlib import Path

from _markers import parse_ide_file
from check_ide import render

IDE = "features/f/addon/ide_addon.py"
STUBS = Path(__file__).resolve().parent / "stubs"  # normalize turns it into a file URI, so it must be absolute


def completion(detail: str) -> str:
    [marker] = parse_ide_file(IDE, "s.cou\n#    ^completion count other\n")
    return render(marker, {"items": [{"label": "count", "detail": detail}]}, STUBS)


def test_completion_of_a_typed_name_passes():
    result = completion("int")
    assert result.splitlines()[0] == "- count: detail: int"
    assert "- other: FAIL: not offered" in result


def test_completion_of_an_unresolved_name_fails():
    # ty offers every name annotated in the add-on's class, typed or not
    assert completion("Unknown").splitlines()[0] == "- count: detail: Unknown FAIL: type not resolved"
    assert "FAIL" in completion("bpy_prop_collection[Unknown]").splitlines()[0]
    assert "FAIL" not in completion("UnknownThing").splitlines()[0]
