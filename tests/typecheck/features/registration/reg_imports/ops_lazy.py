"""Imported inside register()."""

import bpy
from bpy.types import Operator


class REG_IMPORTS_OT_lazy(Operator):
    bl_idname = "reg_imports.lazy"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(REG_IMPORTS_OT_lazy)


def unregister():
    bpy.utils.unregister_class(REG_IMPORTS_OT_lazy)
