"""Signature help and keyword hover: per-parameter documentation (check:ide; never imported)."""

from __future__ import annotations

import bpy
from bpy.types import Object


def uniform_indent(obj: Object) -> None:
    # Docstring with :param lines at the same indent as the summary: parameters are documented.
    obj.select_set(True)
    #              ^signature
    #              ^signature-param "Selection state to define"
    obj.select_set(True, view_layer=None)
    #                    ^hover-contains "Use this instead of the active view layer"


def mixed_indent(obj: Object) -> None:
    # Docstring whose :param lines are indented deeper than the summary (fake-bpy-module): per-parameter
    # docs are lost (hover-docstring-testing.md, section 3.3).
    obj.ray_cast((0, 0, 0), (0, 0, 1))
    #             ^signature
    obj.ray_cast((0, 0, 0), (0, 0, 1), distance=1.0)
    #                                  ^hover-contains "Maximum distance"


def props_functions() -> None:
    bpy.props.IntProperty(name="Count", description="Number of items")
    #                                   ^hover-contains "tooltip"


def operators() -> None:
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    #                               ^signature
    #                               ^signature-param "Size"
