# /// catalog
# title = "Editor members in a menu's `poll`"
# section = "members"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["assumptions"]
#
# [evidence]
# addon = "assumptions/asm_editor_member"
# rule = "blender-assumed-editor-member"
# lenient = "warn"
# default = "warn"
# strict = "error"
#
# [differs]
# "builtin/5.2" = "Blender 5.2's stubs type the callback's `context` as `Context | None`, so every read of it is reported and `area` keeps `None`."
# "fake-bpy-module/5.2" = "These stubs type the callback's `context` as `Context | None`, so every read of it is reported and `area` keeps `None`."
# ///
"""A menu is usually shown in an editor, where `area`, `region` and `space_data` are set, but nothing in a menu
class names that editor. The checker takes the members as not `None` in its `poll` and reports each read as an
Assumption; a read tested for `None` is not reported."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import Area, Menu


class SIMPLE_MT_tools(Menu):
    bl_label = "Tools"

    @classmethod
    def poll(cls, context):
        assert_type(context.area, Area)  # ty: ignore[blender-assumed-editor-member]
        if context.region is None:
            return False
        return context.region.type == "WINDOW"

    def draw(self, context):
        self.layout.label(text="Tools")
