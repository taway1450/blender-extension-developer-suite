"""Operators of the subpackage."""

import bpy
from bpy.types import Operator


class REG_SUBMODULE_FACTORY_OT_package(Operator):
    bl_idname = "reg_submodule_factory.package"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REG_SUBMODULE_FACTORY_OT_unlisted(Operator):  # ty: ignore[blender-unregistered-class]
    bl_idname = "reg_submodule_factory.unlisted"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(REG_SUBMODULE_FACTORY_OT_package)


def unregister():
    bpy.utils.unregister_class(REG_SUBMODULE_FACTORY_OT_package)
