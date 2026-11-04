"""Operators found by auto_load."""

from bpy.types import Operator


class REG_AUTOLOAD_OT_first(Operator):
    bl_idname = "reg_autoload.first"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REG_AUTOLOAD_OT_second(Operator):
    bl_idname = "reg_autoload.second"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}
