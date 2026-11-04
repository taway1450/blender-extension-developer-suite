"""Feature test: properties added to existing Blender types at register time (info_overview.rst:364-449)."""

from __future__ import annotations

import bpy
from bpy.props import FloatProperty, IntProperty, PointerProperty
from bpy.types import PropertyGroup


class PROPS_ON_ID_Settings(PropertyGroup):
    count: IntProperty(name="Count", default=1)


def register() -> None:
    bpy.utils.register_class(PROPS_ON_ID_Settings)
    # The usual form: assign a property definition to an existing type.
    bpy.types.Scene.props_on_id = PointerProperty(type=PROPS_ON_ID_Settings)
    bpy.types.Object.props_on_id_weight = FloatProperty(name="Weight", default=1.0)
    # info_overview.rst also shows `bpy.types.Object.my_float: bpy.props.FloatProperty()`, but Python does
    # not store annotations on attribute targets, so that form registers nothing (checked in Blender 5.4).


def unregister() -> None:
    del bpy.types.Object.props_on_id_weight
    del bpy.types.Scene.props_on_id
    bpy.utils.unregister_class(PROPS_ON_ID_Settings)
