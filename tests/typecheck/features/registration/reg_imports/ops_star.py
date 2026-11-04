"""Star-imported by __init__.py; __init__.py registers the class itself."""

from bpy.types import Operator

__all__ = ["REG_IMPORTS_OT_star"]


class REG_IMPORTS_OT_star(Operator):
    bl_idname = "reg_imports.star"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}
