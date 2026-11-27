# /// catalog
# title = "A child panel registered before its parent"
# section = "order"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["registration_checks"]
# see = ["blender/source/blender/makesrna/intern/rna_ui.cc"]
# ///
"""A panel with `bl_parent_id` is drawn inside the panel of that idname, which must be registered first: otherwise
Blender reports that the parent was not found and the registration fails. The checker reports the child
registered too early."""

import bpy
from bpy.types import Panel

bl_info = {
    "name": "Catalog: a child panel registered before its parent",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


class SUBPANEL_ORDER_PT_parent(Panel):
    bl_label = "Parent"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        pass


class SUBPANEL_ORDER_PT_child(Panel):
    bl_label = "Child"
    bl_parent_id = "SUBPANEL_ORDER_PT_parent"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        pass


def register():
    bpy.utils.register_class(SUBPANEL_ORDER_PT_child)  # ty: ignore[blender-register-order]
    bpy.utils.register_class(SUBPANEL_ORDER_PT_parent)


def unregister():
    bpy.utils.unregister_class(SUBPANEL_ORDER_PT_parent)
    bpy.utils.unregister_class(SUBPANEL_ORDER_PT_child)
