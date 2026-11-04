"""A module two packages down."""

import bpy
from bpy.types import Operator


class REG_IMPORTS_OT_nested(Operator):
    bl_idname = "reg_imports.nested"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(REG_IMPORTS_OT_nested)


def unregister():
    bpy.utils.unregister_class(REG_IMPORTS_OT_nested)
