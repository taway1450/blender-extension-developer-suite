# /// catalog
# title = "`space_data` in a panel of an editor"
# section = "members"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["context_members"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's stubs type the callback's `context` as `Context | None`, so every read of it is reported and `space_data` stays `Space | None`."
# "fake-bpy-module/5.2" = "These stubs type the callback's `context` as `Context | None`, so every read of it is reported and `space_data` stays `Space | None`."
# ///
"""A panel is drawn only in the editor its `bl_space_type` names, so `context.space_data` there is that editor's
`Space` subclass: `SpaceView3D` for `"VIEW_3D"`. The checker types it so. A menu or an operator has no editor of its
own, and keeps the stubs' `Space | None`."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import Panel, SpaceView3D


class Overlay(Panel):
    bl_label = "Overlay"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        assert_type(context.space_data, SpaceView3D)
        self.layout.label(text=f"Lens: {context.space_data.lens}")
