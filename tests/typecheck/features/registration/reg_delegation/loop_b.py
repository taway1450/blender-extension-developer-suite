"""Registered in a loop over modules."""

import bpy
from bpy.types import Operator


class REG_DELEGATION_OT_module_loop_b(Operator):
    bl_idname = "reg_delegation.module_loop_b"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(REG_DELEGATION_OT_module_loop_b)


def unregister():
    bpy.utils.unregister_class(REG_DELEGATION_OT_module_loop_b)
