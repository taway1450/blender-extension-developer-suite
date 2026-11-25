"""The sidebar panels, and two popovers: the display settings and the active object."""

from __future__ import annotations

import os

import bmesh
import bpy
import bpy.utils.previews
from bpy.types import Panel

from . import overlay

# The add-on's own icons, loaded from its folder when it registers.
preview_collections = {}


class VIEW3D_PT_viewport_tools(Panel):
    bl_label = "Viewport Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"

    def draw(self, context):
        layout = self.layout
        icons = preview_collections["main"]
        layout.operator(
            "view3d.viewport_tools_measure", icon_value=icons["ruler"].icon_id
        )
        snapped = layout.operator(
            "view3d.viewport_tools_measure", text="Measure Snapped"
        )
        snapped.snap = True
        layout.operator("view3d.viewport_tools_mark", icon="EMPTY_AXIS")
        if len(overlay.points) == 2:
            first, second = overlay.points
            layout.label(text=f"Distance: {(second - first).length:.3f}")
        layout.popover("VIEW3D_PT_viewport_tools_display", text="Display")


class VIEW3D_PT_viewport_tools_edges(Panel):
    bl_label = "Selected Edges"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"
    bl_context = "mesh_edit"

    def draw(self, context):
        # The sidebar shows a "mesh_edit" panel only while a mesh is edited.
        # demo: blender-narrowed-by-bl-context
        mesh = context.edit_object.data
        bm = bmesh.from_edit_mesh(mesh)
        total = sum(edge.calc_length() for edge in bm.edges if edge.select)
        self.layout.label(text=f"Length: {total:.3f}")


class VIEW3D_PT_viewport_tools_display(Panel):
    bl_label = "Measure Display"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

    def draw(self, context):
        layout = self.layout
        # A popover is drawn in the editor that opens it, and the add-on opens this one in a 3D viewport.
        # demo: blender-narrowed-by-popover
        settings = context.space_data.overlay
        layout.prop(settings, "show_text")
        layout.prop(settings, "show_cursor")


class VIEW3D_PT_viewport_tools_object(Panel):
    bl_label = "Active Object"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

    def draw(self, context):
        layout = self.layout
        # `draw_header` below opens this popover only for an active object, but it is a function
        # appended to Blender's header, and the checker reads only the classes that open a popover.
        # demo: later/popover-opened-by-appended-function
        layout.prop(context.object, "name")


def draw_header(self, context):
    if context.object is not None:
        self.layout.popover(
            "VIEW3D_PT_viewport_tools_object", text="", icon="OBJECT_DATA"
        )


def panel_classes():
    """Every panel of this module, in the order they are defined."""
    # The checker cannot follow a class list built at run time, so it takes every class as registered.
    # demo: blender-assumed-complete-registration
    return [value for name, value in globals().items() if name.startswith("VIEW3D_PT_")]


def register():
    icons = bpy.utils.previews.new()
    icons.load("ruler", os.path.join(os.path.dirname(__file__), "ruler.png"), "IMAGE")
    preview_collections["main"] = icons
    for cls in panel_classes():
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_HT_header.append(draw_header)


def unregister():
    bpy.types.VIEW3D_HT_header.remove(draw_header)
    for cls in reversed(panel_classes()):
        bpy.utils.unregister_class(cls)
    for icons in preview_collections.values():
        bpy.utils.previews.remove(icons)
    preview_collections.clear()
