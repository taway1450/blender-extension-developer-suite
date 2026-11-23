"""Draw handlers: the operator in __init__.py gives draw_outline to SpaceNodeEditor.draw_handler_add, so Blender calls
it while it draws a region of the node editor, and draw_border is called only from it. The checker takes their editor
members as set (space_data as the node editor's space) and reports the reads under blender-assumed-editor-member;
draw_label, also called from elsewhere, keeps the stub types. The assert_type calls are no-ops at runtime."""

from typing import assert_type

import bpy
from bpy.types import Area, Region, Space, SpaceNodeEditor


def draw_outline(operator, context):
    assert_type(bpy.context.space_data, SpaceNodeEditor)  # ty: ignore[blender-assumed-editor-member]
    assert_type(bpy.context.area, Area)  # ty: ignore[blender-assumed-editor-member]
    draw_border(operator)
    draw_label()


def draw_border(operator):
    region = bpy.context.region  # ty: ignore[blender-assumed-editor-member]
    assert_type(region, Region)
    print(region.view2d)


def draw_label():
    assert_type(bpy.context.space_data, Space | None)  # bare-ok: also called outside a draw handler


def report():
    draw_label()
