"""The idname is evaluated before it is looked up."""

from __future__ import annotations

from typing import Literal, assert_type

from bpy.types import OperatorProperties, UILayout, bpy_prop_array

from . import CATEGORY, STEP_IDNAME, OPPROPS_IDNAMES_OT_step


def evaluated(layout: UILayout) -> None:
    assert_type(layout.operator("opprops_idnames.step").factor, float)
    assert_type(layout.operator("OPPROPS_IDNAMES_OT_step").factor, float)
    assert_type(layout.operator(STEP_IDNAME).factor, float)
    assert_type(layout.operator(OPPROPS_IDNAMES_OT_step.bl_idname).factor, float)
    assert_type(layout.operator(f"{CATEGORY}.step").factor, float)  # oracle-skip: stock ty does not evaluate f-strings
    assert_type(layout.operator("opprops_idnames_ot_odd.run").steps, float)
    assert_type(layout.operator("OPPROPS_IDNAMES_OT_ODD_OT_run").steps, float)


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


def conditional(layout: UILayout, enabled: bool) -> None:
    props = layout.operator("wm.owner_disable" if enabled else "wm.owner_enable")
    assert_type(props.owner_id, str)
    props.owner_id = "my_addon"
    props.owner_id = 1  # ty: ignore[invalid-assignment]  # bare-ok: holds bare because the attribute is missing; the assert above needs the checker
    mixed = layout.operator("opprops_idnames.step" if enabled else "opprops_idnames_ot_odd.run")
    mixed.factor  # ty: ignore[missing-union-attribute]  # bare-ok: must stay missing: the odd operator has no factor
    layout.operator("opprops_idnames.step" if enabled else "opprops_idnames.missing")  # ty: ignore[blender-unknown-operator]


def builtin_arrays(layout: UILayout) -> None:
    props = layout.operator("transform.mirror")
    assert_type(props.constraint_axis, bpy_prop_array[bool])
    props.constraint_axis[0] = True
    props.constraint_axis = (True, False, False)
    assert_type(layout.operator("image.resize").size, bpy_prop_array[int])
    assert_type(layout.operator("image.new").color, bpy_prop_array[float])
