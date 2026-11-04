"""Not in the submodule list: never imported, never registered."""

import bpy
from bpy.types import Operator


class REG_SUBMODULE_FACTORY_OT_unlisted_module(Operator):  # ty: ignore[blender-unregistered-class]
    bl_idname = "reg_submodule_factory.unlisted_module"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def register():  # ty: ignore[blender-unreachable-registration]
    bpy.utils.register_class(REG_SUBMODULE_FACTORY_OT_unlisted_module)


def unregister():
    bpy.utils.unregister_class(REG_SUBMODULE_FACTORY_OT_unlisted_module)
