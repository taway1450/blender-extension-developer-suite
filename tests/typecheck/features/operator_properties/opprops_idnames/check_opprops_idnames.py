"""The idname is evaluated before it is looked up."""

from __future__ import annotations

from typing import Literal, assert_type

from bpy.types import OperatorProperties, UILayout

from . import CATEGORY, STEP_IDNAME, OPPROPS_IDNAMES_OT_step


def evaluated(layout: UILayout) -> None:
    assert_type(layout.operator("opprops_idnames.step").factor, float)
    assert_type(layout.operator("OPPROPS_IDNAMES_OT_step").factor, float)
    assert_type(layout.operator(STEP_IDNAME).factor, float)
    assert_type(layout.operator(OPPROPS_IDNAMES_OT_step.bl_idname).factor, float)
    assert_type(layout.operator(f"{CATEGORY}.step").factor, float)  # oracle-skip: stock ty does not evaluate f-strings


def builtin(layout: UILayout) -> None:
    assert_type(layout.operator("object.select_all").action, Literal["TOGGLE", "SELECT", "DESELECT", "INVERT"])
    assert_type(layout.operator("OBJECT_OT_select_all").action, Literal["TOGGLE", "SELECT", "DESELECT", "INVERT"])
    assert_type(layout.operator("mesh.primitive_cube_add").size, float)
    assert_type(layout.operator("mesh.primitive_cube_add").calc_uvs, bool)
    layout.operator("object.select_all").action = "NOPE"  # ty: ignore[invalid-assignment]  # bare-ok: holds bare because the attribute is missing; the asserts above need the checker


def not_known(layout: UILayout, name: str) -> None:
    assert_type(layout.operator(name), OperatorProperties | None)  # bare-ok: the stub type is kept for a non-literal idname
    layout.operator("opprops_idnames.missing")  # ty: ignore[blender-unknown-operator]
    layout.operator("opprops_sinks.step")  # ty: ignore[blender-unknown-operator]
