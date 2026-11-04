"""A submodule registered by register_submodule_factory."""

import bpy
from bpy.types import Operator


class REG_SUBMODULE_FACTORY_OT_module(Operator):
    bl_idname = "reg_submodule_factory.module"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(REG_SUBMODULE_FACTORY_OT_module)


def unregister():
    bpy.utils.unregister_class(REG_SUBMODULE_FACTORY_OT_module)
