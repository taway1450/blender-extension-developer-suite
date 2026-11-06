"""Feature test: update, get, set, poll and items callbacks. Blender calls them with the instance of the class
that declares the property as `self`, so that is their first parameter's type."""

from __future__ import annotations

from typing import assert_type

import bpy
from bpy.props import EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Context, Material, Object, PropertyGroup


def count_update(self: PROPS_CALLBACKS_Settings, context: Context) -> None:
    self.label = str(self.count)


def get_ratio(self: PROPS_CALLBACKS_Settings) -> float:
    return self.get("ratio", 0.0)


def set_ratio(self: PROPS_CALLBACKS_Settings, value: float) -> None:
    self["ratio"] = value


def poll_mesh(self: PROPS_CALLBACKS_Settings, obj: Object) -> bool:
    return obj.type == "MESH"


def mode_items(self: PROPS_CALLBACKS_Settings, context: Context | None):
    return [("A", "A", ""), ("B", "B", "")]


def untyped_update(self, context):
    pass


def get_label_wrong(self: PROPS_CALLBACKS_Settings) -> int:
    return 1


def set_count_wrong(self: PROPS_CALLBACKS_Settings, value: str) -> None:
    pass


def poll_wrong_type(self: PROPS_CALLBACKS_Settings, material: Material) -> bool:
    return True


class PROPS_CALLBACKS_Settings(PropertyGroup):
    count: IntProperty(update=count_update)
    label: StringProperty()
    ratio: FloatProperty(get=get_ratio, set=set_ratio)
    target: PointerProperty(type=Object, poll=poll_mesh)
    mode: EnumProperty(items=mode_items)
    untyped: IntProperty(update=untyped_update)
    # Lambdas get their parameter types from the property they are passed to.
    lambda_update: IntProperty(update=lambda self, context: print(assert_type(self, PROPS_CALLBACKS_Settings).label))
    lambda_poll: PointerProperty(type=Object, poll=lambda self, obj: assert_type(obj, Object).type == "MESH")
    lambda_items: EnumProperty(items=lambda self, context: [(assert_type(self, PROPS_CALLBACKS_Settings).label, "", "")])
    lambda_get: IntProperty(get=lambda self: assert_type(self, PROPS_CALLBACKS_Settings).count)
    # Callbacks with the wrong types. Blender only checks the number of parameters (see props_defaults), so these
    # register and fail when they are called.
    wrong_get: StringProperty(get=get_label_wrong)  # ty: ignore[invalid-argument-type]
    wrong_set: IntProperty(get=lambda self: 0, set=set_count_wrong)  # ty: ignore[invalid-argument-type]
    wrong_poll: PointerProperty(type=Object, poll=poll_wrong_type)  # ty: ignore[invalid-argument-type]


def register():
    bpy.utils.register_class(PROPS_CALLBACKS_Settings)


def unregister():
    bpy.utils.unregister_class(PROPS_CALLBACKS_Settings)
