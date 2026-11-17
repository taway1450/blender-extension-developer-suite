"""Feature test: a `str` (or `set[str]`) value where the stubs have an enum `Literal`.

A value typed `str` is accepted where Blender takes an enum item, as an argument of a Blender function or operator
and as the value of an enum property, and reported (blender-imprecise-enum-value): Blender checks the name itself
and raises for one that is not an item. `set[str]` for an enum flag set likewise. A string literal is precise, so
one that is not an item stays an error. Only Blender's enums: an add-on's own function keeps ty's check."""

from typing import Literal

import bpy
from bpy.types import Bone, Operator, UILayout


def new_light(name: str, light_type: str) -> None:
    bpy.data.lights.new(name, light_type)  # ty: ignore[blender-imprecise-enum-value]
    bpy.data.lights.new(name, type=light_type)  # ty: ignore[blender-imprecise-enum-value]


def set_inherit_scale(bone: Bone, mode: str) -> None:
    bone.inherit_scale = mode  # ty: ignore[blender-imprecise-enum-value]


def mode_button(layout: UILayout, mode: str) -> None:
    props = layout.operator("object.mode_set")
    props.mode = mode  # ty: ignore[blender-imprecise-enum-value]


def enter_mode(mode: str, select_modes: set[str]) -> None:
    bpy.ops.object.mode_set(mode=mode)  # ty: ignore[blender-imprecise-enum-value]
    bpy.ops.object.mode_set_with_submode(mesh_select_mode=select_modes)  # ty: ignore[blender-imprecise-enum-value]


def literals(bone: Bone) -> None:
    bone.inherit_scale = "FULL"  # an item: fine
    bone.inherit_scale = "FULLY"  # ty: ignore[invalid-assignment]  # bare-ok: a name that is not an item stays an error
    bpy.ops.object.mode_set(mode="OBJCT")  # ty: ignore[invalid-argument-type]  # bare-ok: a name that is not an item stays an error
    bpy.ops.object.mode_set_with_submode(mesh_select_mode={"VERT", "EDGEE"})  # ty: ignore[invalid-argument-type]  # bare-ok: a set display holding a name that is not an item stays an error


def own_function(kind: Literal["A", "B"]) -> None:
    pass


def own_enum(kind: str) -> None:
    own_function(kind)  # ty: ignore[invalid-argument-type]  # bare-ok: an add-on's own Literal is not Blender's enum


class IMP_ENUM_VALUE_OT_mode(Operator):
    bl_idname = "imp_enum_value.mode"
    bl_label = "Mode"

    def execute(self, context):
        enter_mode("OBJECT", {"VERT"})
        return {"FINISHED"}


def register():
    bpy.utils.register_class(IMP_ENUM_VALUE_OT_mode)


def unregister():
    bpy.utils.unregister_class(IMP_ENUM_VALUE_OT_mode)
