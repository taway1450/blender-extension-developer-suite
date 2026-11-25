"""The sidebar panels, the list of placed copies and the Object menu entry."""

from __future__ import annotations

import bpy
from bpy.types import Menu, Panel, UIList

from .operators import OBJECT_OT_scatter_tools_clear


class SCATTER_UL_placed(UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        # demo: blender-assumed-list-item
        instance = item.instance
        layout.label(text=item.name, icon="OBJECT_DATA" if instance else "ERROR")


class ScatterPanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Scatter"


class VIEW3D_PT_scatter_tools(ScatterPanel, Panel):
    bl_label = "Scatter Tools"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        settings = context.scene.scatter_tools

        column = layout.column()
        column.prop(settings, "count")
        column.prop(settings, "radius")
        column.prop(settings, "density")
        column.prop(settings, "seed")
        column.prop(settings, "distribution")
        column.prop(settings, "randomize")
        column.prop(settings, "scale_range")
        column.prop(settings, "offset")
        column.prop(settings, "tint")
        column.prop(settings, "target_collection")

        # demo: context_members
        shading = context.space_data.shading
        if shading.color_type != "OBJECT":
            layout.label(text="The tint shows with Object color shading", icon="INFO")

        row = layout.row(align=True)
        row.operator("object.scatter_tools_scatter", icon="PARTICLES")
        # demo: operator_properties
        more = row.operator("object.scatter_tools_scatter", text="", icon="ADD")
        more.keep_previous = True
        row.operator("object.scatter_tools_reseed", text="", icon="FILE_REFRESH")
        if settings.preview_dirty:
            layout.label(text="The settings changed since the last run", icon="ERROR")


class VIEW3D_PT_scatter_tools_surface(ScatterPanel, Panel):
    bl_label = "Surface"
    bl_parent_id = "VIEW3D_PT_scatter_tools"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        settings = context.scene.scatter_tools
        layout.prop(settings, "surface")
        if settings.surface is None:
            layout.operator("object.scatter_tools_ground", icon="MESH_PLANE")


class VIEW3D_PT_scatter_tools_placed(ScatterPanel, Panel):
    bl_label = "Placed Copies"
    bl_parent_id = "VIEW3D_PT_scatter_tools"
    bl_options = {"DEFAULT_CLOSED"}

    # demo: implied_narrowings
    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def draw(self, context):
        layout = self.layout
        settings = context.scene.scatter_tools
        layout.label(text=f"Source: {context.active_object.name}")
        layout.template_list(
            "SCATTER_UL_placed", "", settings, "placed", settings, "active_index"
        )
        layout.operator(OBJECT_OT_scatter_tools_clear.bl_idname, icon="TRASH")


class VIEW3D_MT_scatter_tools(Menu):
    bl_label = "Scatter"

    def draw(self, context):
        layout = self.layout
        layout.operator("object.scatter_tools_scatter")
        layout.operator("object.scatter_tools_reseed")
        layout.operator("object.scatter_tools_clear")
        layout.separator()
        layout.operator("object.scatter_tools_ground")


def draw_object_menu(self, context):
    self.layout.menu("VIEW3D_MT_scatter_tools")


classes = (
    SCATTER_UL_placed,
    VIEW3D_PT_scatter_tools,
    VIEW3D_PT_scatter_tools_surface,
    VIEW3D_PT_scatter_tools_placed,
    VIEW3D_MT_scatter_tools,
)


def register() -> None:
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_object.append(draw_object_menu)


def unregister() -> None:
    bpy.types.VIEW3D_MT_object.remove(draw_object_menu)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
