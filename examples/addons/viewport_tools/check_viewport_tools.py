"""The types the add-on's code relies on. Blender never imports this file (see ../README.md)."""

from __future__ import annotations

from typing import Literal, assert_type

import bpy
from bpy.types import (
    Context,
    Gizmo,
    GizmoGroup,
    ImagePreview,
    Object,
    UILayout,
    WorkSpaceTool,
)


def operator_properties(layout: UILayout, gizmo: Gizmo, tool: WorkSpaceTool) -> None:
    # Every function that takes an operator's idname gives that operator's properties.
    # demo: operator_properties
    assert_type(layout.operator("view3d.viewport_tools_measure").snap, bool)
    assert_type(gizmo.target_set_operator("view3d.viewport_tools_measure").snap, bool)
    assert_type(tool.operator_properties("view3d.viewport_tools_measure").snap, bool)
    layout.operator("view3d.viewport_tools_measure").snapping = True  # ty: ignore[invalid-assignment]
    # demo: operator_calls
    bpy.ops.view3d.viewport_tools_measure("INVOKE_DEFAULT", snap=True)


def built_in_gizmos(group: GizmoGroup) -> None:
    # A built-in gizmo type has properties of its own, which the stubs do not list.
    arrow = group.gizmos.new("GIZMO_GT_arrow_3d")
    # demo: later/builtin-gizmo-types
    assert_type(arrow.draw_style, Literal["NORMAL", "CROSS", "BOX", "CONE", "PLANE"])


def preview_icons() -> None:
    icons = bpy.utils.previews.new()
    # demo: bpy_symbols
    assert_type(icons.load("ruler", "ruler.png", "IMAGE"), ImagePreview)
    # A preview collection is a dictionary of previews, which the builtin stubs do not say.
    # demo: later/preview-icons
    assert_type(icons["ruler"].icon_id, int)


def outside_the_callbacks(context: Context) -> None:
    # What a callback may rely on holds only there: elsewhere the context promises nothing.
    assert_type(context.object, Object | None)
    context.space_data.overlay  # ty: ignore[missing-attribute]
