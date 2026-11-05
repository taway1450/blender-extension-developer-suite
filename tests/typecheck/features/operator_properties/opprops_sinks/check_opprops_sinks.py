"""Each sink gives the properties of the operator its idname names."""

from __future__ import annotations

from typing import Literal, assert_type

from bpy.types import Gizmo, KeyMap, UILayout, WindowManager, WorkSpaceTool

from . import OPPROPS_SINKS_OT_bare, OPPROPS_SINKS_OT_combo, OPPROPS_SINKS_OT_step


def layout_operator(layout: UILayout) -> None:
    props = layout.operator("opprops_sinks.step")
    assert_type(props.amount, int)
    assert_type(props.mode, Literal["A", "B"])
    assert_type(props.label, str)
    assert_type(props.flags, set[Literal["A", "B"]])
    props.amount = 2
    props.amount = "2"  # ty: ignore[invalid-assignment]  # bare-ok: holds bare because the attribute is missing; the asserts above need the checker
    props.mode = "C"  # ty: ignore[invalid-assignment]  # bare-ok: holds bare because the attribute is missing; the asserts above need the checker
    props.missing  # ty: ignore[unresolved-attribute]  # bare-ok: must stay missing: ty-blender must not add it
    assert_type(layout.operator("OPPROPS_SINKS_OT_step", text="Step", icon="ADD").amount, int)
    layout.operator("opprops_sinks.bare").amount  # ty: ignore[unresolved-attribute]  # bare-ok: must stay missing: ty-blender must not add it


def other_layout_functions(layout: UILayout) -> None:
    props = layout.operator_menu_hold("opprops_sinks.step", menu="VIEW3D_MT_object")
    assert_type(props.amount, int)
    assert_type(props.mode, Literal["A", "B"])
    assert_type(props.label, str)
    assert_type(props.flags, set[Literal["A", "B"]])
    assert_type(layout.operator_menu_enum("opprops_sinks.step", "mode").amount, int)
    layout.operator_enum("opprops_sinks.step", "flags")
    layout.operator_enum("opprops_sinks.step", "amount")  # ty: ignore[blender-invalid-operator-property]
    layout.operator_menu_enum("opprops_sinks.step", "missing")  # ty: ignore[blender-invalid-operator-property]


def keymap_items(keymap: KeyMap) -> None:
    item = keymap.keymap_items.new("opprops_sinks.step", "S", "PRESS")
    props = item.properties
    assert_type(props.amount, int)
    assert_type(props.mode, Literal["A", "B"])
    assert_type(props.label, str)
    assert_type(props.flags, set[Literal["A", "B"]])
    item.properties.mode = "C"  # ty: ignore[invalid-assignment]  # bare-ok: holds bare because the attribute is missing; the asserts above need the checker


def last_properties(wm: WindowManager) -> None:
    props = wm.operator_properties_last("opprops_sinks.step")
    assert_type(props.amount, int)
    assert_type(props.mode, Literal["A", "B"])
    assert_type(props.label, str)
    assert_type(props.flags, set[Literal["A", "B"]])


def gizmo_and_tool(gizmo: Gizmo, tool: WorkSpaceTool) -> None:
    props = gizmo.target_set_operator("opprops_sinks.step")
    assert_type(props.amount, int)
    assert_type(props.mode, Literal["A", "B"])
    assert_type(props.label, str)
    assert_type(props.flags, set[Literal["A", "B"]])
    props = tool.operator_properties("OPPROPS_SINKS_OT_step")
    assert_type(props.amount, int)
    assert_type(props.mode, Literal["A", "B"])
    assert_type(props.label, str)
    assert_type(props.flags, set[Literal["A", "B"]])


def macro() -> None:
    props = OPPROPS_SINKS_OT_combo.define("OPPROPS_SINKS_OT_step").properties
    assert_type(props.amount, int)
    assert_type(props.mode, Literal["A", "B"])
    assert_type(props.label, str)
    assert_type(props.flags, set[Literal["A", "B"]])


def own_properties(step: OPPROPS_SINKS_OT_step, bare: OPPROPS_SINKS_OT_bare) -> None:
    props = step.properties
    assert_type(props.amount, int)
    assert_type(props.mode, Literal["A", "B"])
    assert_type(props.label, str)
    assert_type(props.flags, set[Literal["A", "B"]])
    bare.properties.amount  # ty: ignore[unresolved-attribute]
