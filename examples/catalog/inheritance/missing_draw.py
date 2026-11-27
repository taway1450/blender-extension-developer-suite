# /// catalog
# title = "A panel without `draw`"
# section = "overrides"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["inheritance"]
#
# [evidence]
# addon = "inheritance/generated/inh_invalid_panel_no_draw"
# register = "fails"
# says = "a Panel without draw"
# ///
"""Most callbacks are optional, but a `Panel`, `Menu`, `Header` or `NodeSocket` must define `draw`: Blender refuses
to register the class without one. The checker reports the class."""

import bpy
from bpy.types import Panel

bl_info = {
    "name": "Catalog: a panel without draw",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


class MISSING_DRAW_PT_tools(Panel):  # ty: ignore[blender-missing-callback]
    bl_label = "Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"


def register():
    bpy.utils.register_class(MISSING_DRAW_PT_tools)


def unregister():
    bpy.utils.unregister_class(MISSING_DRAW_PT_tools)
