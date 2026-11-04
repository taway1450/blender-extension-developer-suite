"""Registered in a loop over modules."""

import bpy
from bpy.types import Operator


class REG_DELEGATION_OT_module_loop_a(Operator):
    bl_idname = "reg_delegation.module_loop_a"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(REG_DELEGATION_OT_module_loop_a)


def unregister():
    bpy.utils.unregister_class(REG_DELEGATION_OT_module_loop_a)
