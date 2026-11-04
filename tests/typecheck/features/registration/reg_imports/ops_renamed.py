"""Its register() is imported under another name."""

import bpy
from bpy.types import Operator


class REG_IMPORTS_OT_renamed(Operator):
    bl_idname = "reg_imports.renamed"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(REG_IMPORTS_OT_renamed)


def unregister():
    bpy.utils.unregister_class(REG_IMPORTS_OT_renamed)
