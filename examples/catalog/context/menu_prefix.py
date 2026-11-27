# /// catalog
# title = "A menu's idname prefix"
# section = "narrowings"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["implied_narrowings"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's stubs type the callback's `context` as `Context | None`, so every read of it is reported and `space_data` stays `Space | None`."
# "fake-bpy-module/5.2" = "These stubs type the callback's `context` as `Context | None`, so every read of it is reported and `space_data` stays `Space | None`."
# ///
"""A menu has no `bl_space_type` and can be opened from any editor, but by convention its idname starts with the
prefix of the editor it belongs to: `VIEW3D_MT_` for the 3D Viewport. The checker takes `space_data` in such a menu as
that editor's `Space` subclass and reports the read as an Implied narrowing."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import Menu, SpaceView3D


class VIEW3D_MT_overlay_extras(Menu):
    bl_label = "Overlay extras"

    def draw(self, context):
        assert_type(context.space_data, SpaceView3D)  # ty: ignore[blender-narrowed-by-menu-prefix]
