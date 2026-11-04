"""The class is imported by __init__.py, which registers it."""

from bpy.types import Operator


class REG_IMPORTS_OT_class_import(Operator):
    bl_idname = "reg_imports.class_import"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}
