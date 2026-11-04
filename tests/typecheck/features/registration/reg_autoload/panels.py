"""A panel and an operator found by auto_load."""

from bpy.types import Operator, Panel


class REG_AUTOLOAD_PT_panel(Panel):
    bl_label = "Autoload"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        self.layout.operator("reg_autoload.panel_helper")


class REG_AUTOLOAD_OT_panel_helper(Operator):
    bl_idname = "reg_autoload.panel_helper"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}
