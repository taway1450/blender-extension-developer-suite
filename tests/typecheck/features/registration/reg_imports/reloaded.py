"""Imported with the importlib.reload pattern."""

import bpy
from bpy.types import Operator


class REG_IMPORTS_OT_reloaded(Operator):
    bl_idname = "reg_imports.reloaded"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(REG_IMPORTS_OT_reloaded)


def unregister():
    bpy.utils.unregister_class(REG_IMPORTS_OT_reloaded)
