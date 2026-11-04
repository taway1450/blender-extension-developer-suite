"""Feature test: a sidebar panel written like scripts/templates_py/ui_panel.py."""

from __future__ import annotations

import bpy
from bpy.types import Context, Panel


class PANEL_DRAW_PT_example(Panel):
    bl_label = "Panel Draw"
    bl_idname = "PANEL_DRAW_PT_example"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Feature Tests"

    @classmethod
    def poll(cls, context: Context) -> bool:
        return context.object is not None

    def draw_header(self, context: Context) -> None:
        self.layout.label(text="", icon="OBJECT_DATA")

    def draw(self, context: Context) -> None:
        layout = self.layout
        obj = context.object
        assert obj is not None
        layout.use_property_split = True
        row = layout.row(align=True)
        row.prop(obj, "name")
        col = layout.column()
        col.prop(obj, "location")
        box = layout.box()
        box.label(text="Active object: " + obj.name, icon="INFO")
        props = layout.operator("object.select_all", text="Select all")
        props.action = "SELECT"


def register() -> None:
    bpy.utils.register_class(PANEL_DRAW_PT_example)


def unregister() -> None:
    bpy.utils.unregister_class(PANEL_DRAW_PT_example)
