"""Feature test: Blender draws a Panel in its bl_space_type, so context.space_data is that editor's Space subclass, but
a panel opened as a popover (layout.popover, wm.call_panel) is drawn with the area of whatever editor opened it. In a
panel the add-on opens as a popover the checker keeps the bl_space_type subclass and reports the read under
blender-narrowed-by-popover; a panel it never opens so stays silent. The assert_type calls in the bodies are no-ops at
runtime."""

from typing import assert_type

import bpy
from bpy.types import Area, Operator, Panel, SpaceView3D


class NAR_POPOVER_PT_settings(Panel):
    bl_label = "Settings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

    def draw(self, context):
        assert_type(context.space_data, SpaceView3D)  # ty: ignore[blender-narrowed-by-popover]
        assert_type(context.area, Area)


class NarPopoverCalled(Panel):
    bl_idname = "NAR_POPOVER_PT_called"
    bl_label = "Called"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"

    def draw(self, context):
        self.layout.prop(context.space_data, "lens")  # ty: ignore[blender-narrowed-by-popover]


class NAR_POPOVER_PT_region(Panel):
    bl_label = "Region"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        assert_type(context.space_data, SpaceView3D)  # drawn only in its region: a silent guarantee
        self.layout.popover("NAR_POPOVER_PT_settings")


class NAR_POPOVER_OT_open(Operator):
    bl_idname = "nar_popover.open"
    bl_label = "Open"

    def execute(self, context):
        bpy.ops.wm.call_panel(name="NAR_POPOVER_PT_called")
        return {"FINISHED"}


classes = (NAR_POPOVER_PT_settings, NarPopoverCalled, NAR_POPOVER_PT_region, NAR_POPOVER_OT_open)
register, unregister = bpy.utils.register_classes_factory(classes)
