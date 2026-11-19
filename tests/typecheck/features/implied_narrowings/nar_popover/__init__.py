"""Feature test: Blender draws a Panel in its bl_space_type, so context.space_data is that editor's Space subclass, but
a panel opened as a popover (layout.popover, wm.call_panel) is drawn with the area of whatever editor opened it. In a
panel the add-on opens as a popover the checker keeps the bl_space_type subclass and reports the read under
blender-narrowed-by-popover; a panel it never opens so stays silent. A popover is drawn with the context of
the editor that opened it, so a HEADER panel (drawn only as a popover) knows what every function opening it checked
before the call, also reported under blender-narrowed-by-popover. The assert_type calls in the bodies are no-ops at
runtime."""

from typing import assert_type

import bpy
from bpy.types import Area, Header, Mesh, Object, Operator, Panel, SpaceView3D


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


class NAR_POPOVER_PT_mesh(Panel):
    bl_label = "Mesh"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

    def draw(self, context):
        assert_type(context.object.data, Mesh)  # ty: ignore[blender-narrowed-by-popover]


class NAR_POPOVER_PT_object(Panel):
    bl_label = "Object"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

    def draw(self, context):
        self.layout.label(text=context.object.name)  # ty: ignore[blender-narrowed-by-popover]


class NAR_POPOVER_PT_anywhere(Panel):
    bl_label = "Anywhere"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

    def draw(self, context):
        assert_type(context.object, Object | None)  # bare-ok: also opened where nothing was checked


class NAR_POPOVER_PT_window(Panel):
    bl_label = "Window"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"

    def draw(self, context):
        assert_type(context.object, Object | None)  # bare-ok: also drawn in its region, unchecked


class NAR_POPOVER_HT_header(Header):
    bl_space_type = "VIEW_3D"

    def draw(self, context):
        layout = self.layout
        ob = context.object
        if ob is not None and ob.type == 'MESH':
            layout.popover("NAR_POPOVER_PT_mesh")
            layout.popover("NAR_POPOVER_PT_anywhere")
            layout.popover("NAR_POPOVER_PT_window")
        layout.popover("NAR_POPOVER_PT_anywhere")
        if ob is None:
            return
        layout.popover("NAR_POPOVER_PT_object")


classes = (NAR_POPOVER_PT_settings, NarPopoverCalled, NAR_POPOVER_PT_region, NAR_POPOVER_OT_open, NAR_POPOVER_PT_mesh,
           NAR_POPOVER_PT_object, NAR_POPOVER_PT_anywhere, NAR_POPOVER_PT_window, NAR_POPOVER_HT_header)
register, unregister = bpy.utils.register_classes_factory(classes)
