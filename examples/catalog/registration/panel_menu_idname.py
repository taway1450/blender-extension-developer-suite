# /// catalog
# title = "Panel and menu idnames without `_PT_` or `_MT_`"
# section = "idnames"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["registration_checks"]
# see = ["blender/source/blender/makesrna/intern/rna_access.cc", "blender/source/blender/makesrna/intern/rna_ui.cc"]
# ///
"""A panel's `bl_idname` contains `_PT_` and a menu's `_MT_`, with text before and after: `OBJECT_PT_tools`. Without
`bl_idname` the class name is used. Blender still registers a class that breaks the convention, with a warning its
source marks as temporary until add-ons update; the checker reports it as an error already."""

import bpy
from bpy.types import Menu, Panel

bl_info = {
    "name": "Catalog: panel and menu idnames",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


class PANEL_MENU_IDNAME_PT_tools(Panel):
    bl_label = "Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        pass


class ToolsPanel(Panel):  # ty: ignore[blender-invalid-idname]
    bl_label = "Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        pass


class PANEL_MENU_IDNAME_MT_tools(Menu):
    bl_idname = "panel_menu_idname.tools"  # ty: ignore[blender-invalid-idname]
    bl_label = "Tools"

    def draw(self, context):
        pass


classes = (PANEL_MENU_IDNAME_PT_tools, ToolsPanel, PANEL_MENU_IDNAME_MT_tools)
register, unregister = bpy.utils.register_classes_factory(classes)
