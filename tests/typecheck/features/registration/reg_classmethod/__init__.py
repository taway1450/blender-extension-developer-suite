"""Feature test: a PropertyGroup's register() classmethod, which Blender calls from register_class, assigns
properties to Blender classes and registers more classes, as Cycles does (`Scene.cycles`). Its unregister()
classmethod, which unregister_class calls, deletes them again."""

import bpy
from bpy.props import IntProperty, PointerProperty
from bpy.types import PropertyGroup


class REG_CLASSMETHOD_PG_object(PropertyGroup):
    """Registered only by REG_CLASSMETHOD_PG_scene.register()."""

    weight: IntProperty()


class REG_CLASSMETHOD_PG_scene(PropertyGroup):
    count: IntProperty()

    @classmethod
    def register(cls):
        bpy.types.Scene.reg_classmethod = PointerProperty(
            name="Settings",
            type=cls,
        )
        bpy.utils.register_class(REG_CLASSMETHOD_PG_object)
        bpy.types.Object.reg_classmethod = PointerProperty(type=REG_CLASSMETHOD_PG_object)

    @classmethod
    def unregister(cls):
        del bpy.types.Object.reg_classmethod
        bpy.utils.unregister_class(REG_CLASSMETHOD_PG_object)
        del bpy.types.Scene.reg_classmethod


class REG_CLASSMETHOD_PG_never(PropertyGroup):  # ty: ignore[blender-unregistered-class]
    @classmethod
    def register(cls):
        bpy.types.Scene.reg_classmethod_never = PointerProperty(type=cls)  # ty: ignore[unresolved-attribute]  # bare-ok: never registered: ty-blender must not add it

    @classmethod
    def unregister(cls):
        del bpy.types.Scene.reg_classmethod_never  # ty: ignore[unresolved-attribute]  # bare-ok: never registered: ty-blender must not add it


def register():
    bpy.utils.register_class(REG_CLASSMETHOD_PG_scene)


def unregister():
    bpy.utils.unregister_class(REG_CLASSMETHOD_PG_scene)
