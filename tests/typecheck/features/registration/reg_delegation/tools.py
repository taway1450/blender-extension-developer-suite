"""A module whose register() is called as tools.register()."""

import bpy
from bpy.types import Operator


class REG_DELEGATION_OT_module_call(Operator):
    bl_idname = "reg_delegation.module_call"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(REG_DELEGATION_OT_module_call)


def unregister():
    bpy.utils.unregister_class(REG_DELEGATION_OT_module_call)
