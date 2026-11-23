"""Feature test: register_class calls a PropertyGroup's register() as `cls.register()`, without arguments. A plain
method `register(self)` raises TypeError there before its body runs, so register_class fails and the property its
body assigns never exists (checked in Blender 5.4)."""

import bpy
from bpy.props import IntProperty
from bpy.types import PropertyGroup


class REG_CLASSMETHOD_PLAIN_PG_scene(PropertyGroup):
    def register(self):
        bpy.types.Scene.reg_classmethod_plain = IntProperty()  # ty: ignore[missing-attribute]  # bare-ok: never run: ty-blender must not add it

    def unregister(self):
        del bpy.types.Scene.reg_classmethod_plain  # ty: ignore[missing-attribute]  # bare-ok: never run: ty-blender must not add it


def register():
    bpy.utils.register_class(REG_CLASSMETHOD_PLAIN_PG_scene)


def unregister():
    bpy.utils.unregister_class(REG_CLASSMETHOD_PLAIN_PG_scene)
