"""The rules for merging reference-stub deltas into the bpy stubs (tests/typecheck/README.md, "Reference stubs and the
oracle"). Every oracle verdict rests on them: a merge bug looks exactly like a wrong marker."""

import os
from textwrap import dedent

import pytest

from _common import StepError
from check_oracle import StubOverlay, merge_delta


def merge(stub: str, delta: str) -> str:
    return merge_delta(dedent(stub), dedent(delta))


def test_a_member_of_an_existing_class_replaces_the_stubs_member():
    stub = """\
        class Scene:
            count: int
            def frame(self) -> int: ...
        """
    assert merge(stub, "class Scene:\n    count: float\n") == dedent(
        """\
        class Scene:
            count: float
            def frame(self) -> int: ...
        """
    )


def test_a_new_member_is_added_at_the_end_of_the_class():
    stub = """\
        class Scene:
            count: int

        class Object: ...
        """
    assert merge(stub, "class Scene:\n    extra: str\n") == dedent(
        """\
        class Scene:
            count: int
            extra: str

        class Object: ...
        """
    )


def test_an_overload_goes_in_front_and_the_existing_definition_becomes_the_last_overload():
    stub = """\
        class UILayout:
            def operator(self, idname: str) -> OperatorProperties: ...
        """
    delta = """\
        from typing import Literal
        class UILayout:
            @overload
            def operator(self, idname: Literal["my.run"]) -> MyProps: ...
        """
    assert merge(stub, delta) == dedent(
        """\
        from typing import Literal
        from typing import overload
        class UILayout:
            @overload
            def operator(self, idname: Literal["my.run"]) -> MyProps: ...
            @overload
            def operator(self, idname: str) -> OperatorProperties: ...
        """
    )


def test_an_overload_of_an_overloaded_function_needs_no_extra_decorator():
    stub = """\
        from typing import overload
        @overload
        def get(key: int) -> int: ...
        @overload
        def get(key: str) -> str: ...
        """
    delta = """\
        @overload
        def get(key: bytes) -> bytes: ...
        """
    assert merge(stub, delta) == dedent(
        """\
        from typing import overload
        @overload
        def get(key: bytes) -> bytes: ...
        @overload
        def get(key: int) -> int: ...
        @overload
        def get(key: str) -> str: ...
        """
    )


def test_a_plain_definition_replaces_every_existing_overload():
    stub = """\
        @overload
        def get(key: int) -> int: ...
        @overload
        def get(key: str) -> str: ...
        def other() -> None: ...
        """
    assert merge(stub, "def get(key: object) -> object: ...\n") == dedent(
        """\
        def get(key: object) -> object: ...
        def other() -> None: ...
        """
    )


def test_a_class_with_other_bases_replaces_the_stubs_class():
    stub = """\
        class bpy_prop_array:
            def foreach_get(self, seq) -> None: ...
        """
    delta = """\
        class bpy_prop_array(Generic[T]):
            def __getitem__(self, key: int) -> T: ...
        """
    assert merge(stub, delta) == dedent(delta)


def test_a_class_with_other_type_parameters_replaces_the_stubs_class():
    stub = "class bpy_prop_collection[T]:\n    x: int\n"
    delta = "class bpy_prop_collection[T, K]:\n    y: int\n"
    assert merge(stub, delta) == delta


def test_a_class_restating_the_same_bases_is_merged_not_replaced():
    stub = "class Panel(bpy_struct):\n    bl_label: str\n"
    assert merge(stub, "class Panel(bpy_struct):\n    bl_idname: str\n") == (
        "class Panel(bpy_struct):\n    bl_label: str\n    bl_idname: str\n"
    )


def test_anything_else_is_appended_and_delta_docstrings_are_dropped():
    stub = "def run() -> None: ...\n"
    delta = '"""Delta for my operators."""\nclass MY_OT_run: ...\nVALUE: int\n'
    assert merge(stub, delta) == "def run() -> None: ...\nclass MY_OT_run: ...\nVALUE: int\n"


@pytest.mark.parametrize(
    ("head", "imports_after"),
    [
        ("from __future__ import annotations\nimport typing\n", 1),
        ('"""Stubs."""\nimport typing\n', 1),
        ('"""Stubs\n\non two lines."""\nimport typing\n', 3),
        ("import typing\n", 0),
    ],
)
def test_imports_go_after_the_future_import_or_the_module_docstring(head, imports_after):
    merged = merge(head + "x: int\n", "from mathutils import Vector\nx: Vector\n").splitlines()
    assert merged[imports_after] == "from mathutils import Vector"
    assert merged[-1] == "x: Vector"


# --- the overlay: copies of the stub packages with the deltas merged in ------------------------------------------------


def write(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def stubs(tmp_path):
    root = tmp_path / "stubs"
    write(root / "bpy" / "__init__.pyi", "")
    write(root / "bpy" / "types" / "__init__.pyi", "class Scene:\n    count: int\n")
    write(root / "bpy" / "ops" / "__init__.pyi", "")
    write(root / "bpy" / "utils.pyi", "def register_class(cls) -> None: ...\n")
    return root


def test_overlay_merges_into_a_copy_and_leaves_the_stubs_alone(tmp_path, stubs):
    write(tmp_path / "deltas" / "bpy.types.pyi", "class Scene:\n    count: float\n")
    StubOverlay([stubs]).build(tmp_path / "deltas", tmp_path / "out")
    assert (tmp_path / "out" / "bpy" / "types" / "__init__.pyi").read_text() == "class Scene:\n    count: float\n"
    assert (stubs / "bpy" / "types" / "__init__.pyi").read_text() == "class Scene:\n    count: int\n"
    # untouched files are shared with the stubs (hard links where the file system has them)
    copy = tmp_path / "out" / "bpy" / "utils.pyi"
    assert copy.read_text() == (stubs / "bpy" / "utils.pyi").read_text()


def test_overlay_creates_a_module_the_stubs_lack(tmp_path, stubs):
    write(tmp_path / "deltas" / "bpy.ops.my_cat.pyi", "def run() -> set[str]: ...\n")
    StubOverlay([stubs]).build(tmp_path / "deltas", tmp_path / "out")
    assert (tmp_path / "out" / "bpy" / "ops" / "my_cat.pyi").read_text() == "def run() -> set[str]: ...\n"
    assert not (stubs / "bpy" / "ops" / "my_cat.pyi").exists()


def test_overlay_merges_onto_an_earlier_overlay(tmp_path, stubs):
    """The oracle baseline is an overlay too; an add-on's deltas go on top of it, not on the bare stubs."""
    write(tmp_path / "base" / "bpy.types.pyi", "class Scene:\n    frame: int\n")
    StubOverlay([stubs]).build(tmp_path / "base", tmp_path / "baseline")
    write(tmp_path / "deltas" / "bpy.types.pyi", "class Scene:\n    count: float\n")
    StubOverlay([tmp_path / "baseline", stubs]).build(tmp_path / "deltas", tmp_path / "out")
    merged = (tmp_path / "out" / "bpy" / "types" / "__init__.pyi").read_text()
    assert merged == "class Scene:\n    count: float\n    frame: int\n"


def test_overlay_cannot_create_a_module_without_its_parent_package(tmp_path, stubs):
    write(tmp_path / "deltas" / "bpy.nowhere.inner.pyi", "x: int\n")
    with pytest.raises(StepError, match="parent package 'bpy.nowhere'"):
        StubOverlay([stubs]).build(tmp_path / "deltas", tmp_path / "out")


def test_overlay_rejects_a_package_no_stubs_provide(tmp_path, stubs):
    write(tmp_path / "deltas" / "numpy.pyi", "x: int\n")
    with pytest.raises(StepError, match="No stubs provide the package of numpy"):
        StubOverlay([stubs]).build(tmp_path / "deltas", tmp_path / "out")


@pytest.mark.skipif(not hasattr(os, "link"), reason="no hard links")
def test_overlay_never_writes_through_a_hard_link(tmp_path, stubs):
    """The copy starts as hard links to the stubs; a merged file must be replaced, not written in place."""
    write(tmp_path / "deltas" / "bpy.utils.pyi", "def unregister_class(cls) -> None: ...\n")
    StubOverlay([stubs]).build(tmp_path / "deltas", tmp_path / "out")
    assert (stubs / "bpy" / "utils.pyi").read_text() == "def register_class(cls) -> None: ...\n"
