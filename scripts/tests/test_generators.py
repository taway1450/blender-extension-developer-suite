"""The feature generators and features:generate: what they write must be valid, reproducible, and kept in step."""

import ast
import importlib
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from _common import StepError
from _features import FEATURES_DIR, GENERATED
from _markers import parse_type_file
from generate_features import (
    GENERATORS_DIR,
    ROOTS_BEGIN,
    ROOTS_END,
    diff,
    generated_files,
    updated_ty_toml,
)

SCRIPTS = Path(__file__).resolve().parent.parent
GENERATORS = sorted(p.stem for p in GENERATORS_DIR.glob("*.py") if not p.name.startswith("_"))


def generate(name: str) -> dict[str, str]:
    return importlib.import_module(f"feature_generators.{name}").generate()


def test_every_generator_belongs_to_a_feature():
    assert GENERATORS  # bpy_symbols, inheritance, properties, ...
    assert all((FEATURES_DIR / name).is_dir() for name in GENERATORS)


@pytest.mark.parametrize("name", GENERATORS)
def test_the_output_does_not_depend_on_the_hash_seed(name):
    """Set and dict iteration order of strings changes with PYTHONHASHSEED; the committed files must not."""
    code = f"import json; from feature_generators import {name} as g; print(json.dumps(g.generate()))"

    def run(seed: str) -> dict[str, str]:
        env = {**os.environ, "PYTHONHASHSEED": seed}
        out = subprocess.run([sys.executable, "-c", code], cwd=SCRIPTS, env=env, capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)

    first, second = run("1"), run("2")
    assert list(first) == list(second)  # same files in the same order
    assert first == second


@pytest.mark.parametrize("name", GENERATORS)
def test_every_file_is_valid(name):
    for rel, text in generate(name).items():
        assert not rel.startswith("/") and ".." not in rel.split("/"), rel
        assert text.endswith("\n") and "\r" not in text, rel
        if rel.endswith(".py"):
            ast.parse(text, filename=rel)
        elif rel.endswith(".toml"):
            tomllib.loads(text)


@pytest.mark.parametrize("name", GENERATORS)
def test_every_addon_is_a_package_with_markers_and_says_it_is_generated(name):
    files = generate(name)
    addons = {rel.split("/")[0] for rel in files}
    for addon in addons:
        assert f"{addon}/__init__.py" in files
        # in check_*.py, or in the add-on's own code (a rejected override is marked where it is written)
        markers = [
            m
            for rel, text in files.items()
            if rel.startswith(f"{addon}/") and rel.endswith(".py")
            for m in parse_type_file(rel, text).markers
        ]
        assert markers, f"{addon} tests nothing"
    for rel, text in files.items():
        if rel.endswith(".py"):
            assert "do not edit" in text, f"{rel} does not say it is generated"


def test_generated_files_go_to_their_features_generated_folder():
    for path in generated_files():
        feature = path.relative_to(FEATURES_DIR).parts[0]
        assert path.is_relative_to(FEATURES_DIR / feature / GENERATED)


# --- what features:generate writes, and what --check reports ----------------------------------------------------------


def test_diff_finds_new_changed_and_stale_files():
    a, b, c, d = (Path(name) for name in "abcd")
    changes = diff({a: "same", b: "new text", c: "brand new"}, {a: "same", b: "old text", d: "gone"})
    assert changes.changed == [b, c]
    assert changes.missing == [c]
    assert changes.stale == {d}
    assert changes


def test_diff_of_identical_files_is_empty():
    files = {Path("a"): "x"}
    assert not diff(files, dict(files))


TY_TOML = f"""\
[environment]
# a comment kept as it is
{ROOTS_BEGIN}
root = [
    "features/old",
]
{ROOTS_END}

[rules]
x = "error"
"""


def test_updated_ty_toml_replaces_only_the_roots():
    text = updated_ty_toml(TY_TOML, ["features/a", "features/a/generated"])
    assert text == TY_TOML.replace('    "features/old",\n', '    "features/a",\n    "features/a/generated",\n')
    assert tomllib.loads(text)["environment"]["root"] == ["features/a", "features/a/generated"]


def test_updated_ty_toml_is_stable():
    once = updated_ty_toml(TY_TOML, ["features/a"])
    assert updated_ty_toml(once, ["features/a"]) == once


def test_updated_ty_toml_needs_the_block():
    with pytest.raises(StepError, match="generated roots"):
        updated_ty_toml("[environment]\n", ["features/a"])
