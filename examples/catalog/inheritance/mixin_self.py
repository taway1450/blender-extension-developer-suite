# /// catalog
# title = "A mixin's `self`"
# section = "mixins"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["inheritance"]
# ///
"""A mixin shares code between Blender classes without deriving from one, so Python alone types `self` in its methods
as the bare mixin, with no `layout`. In Blender `self` is always one of the classes that use the mixin, and the
checker types it so: here both are panels, so `self` is a `Panel` too. Only members that every class using the mixin
has resolve: a panel has no `report`."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import Panel, UILayout


class ToolsMixin:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw_header_row(self, context):
        assert_type(self.layout, UILayout)
        self.layout.label(text=self.bl_label)
        self.report({"INFO"}, "drawn")  # ty: ignore[missing-attribute]


class MeshTools(ToolsMixin, Panel):
    bl_label = "Mesh tools"

    def draw(self, context):
        self.draw_header_row(context)


class CurveTools(ToolsMixin, Panel):
    bl_label = "Curve tools"

    def draw(self, context):
        self.draw_header_row(context)
