# /// catalog
# title = "A panel opened as a popover"
# section = "popovers"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["implied_narrowings"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's stubs type the callback's `context` as `Context | None`, so every read of it is reported and `space_data` stays `Space | None`."
# "fake-bpy-module/5.2" = "These stubs type the callback's `context` as `Context | None`, so every read of it is reported and `space_data` stays `Space | None`."
# ///
"""In a panel the add-on opens as a popover, `context.space_data` is reported as an Implied narrowing. A panel is
drawn in its `bl_space_type`, so `space_data` there is that editor's `Space` subclass; opened as a popover, from
`layout.popover` or `wm.call_panel`, it is drawn with the area of whatever editor opened it, which is the same editor
only by convention. The checker keeps the subclass and reports the read."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import Panel, SpaceView3D


class POPOVER_PANEL_PT_lens(Panel):
    bl_label = "Lens"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

    def draw(self, context):
        assert_type(context.space_data, SpaceView3D)  # ty: ignore[blender-narrowed-by-popover]


class POPOVER_PANEL_PT_view(Panel):
    bl_label = "View"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        self.layout.popover("POPOVER_PANEL_PT_lens")
