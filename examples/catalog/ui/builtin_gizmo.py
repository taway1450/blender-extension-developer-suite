# /// catalog
# title = "Blender's own gizmo types"
# section = "gizmos-tools"
# status = "not-handled"
# features = ["api_types"]
# later = "builtin-gizmo-types"
#
# [future]
# class = "planned"
# note = "Type `gizmos.new` by the gizmo type it names, with that type's properties."
# tracked = "later/builtin-gizmo-types"
# ///
"""A gizmo group creates its gizmos with `self.gizmos.new("GIZMO_GT_arrow_3d")`, and each of Blender's gizmo types has
its own properties, such as an arrow's `draw_style`. The stubs return a plain `Gizmo`, which has none of them, so
setting one is reported."""

from bpy.types import GizmoGroup


class LightGizmos(GizmoGroup):
    bl_label = "Light"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_options = {"3D", "PERSISTENT"}

    def setup(self, context):
        arrow = self.gizmos.new("GIZMO_GT_arrow_3d")
        # gap: the arrow's own properties are not known
        arrow.draw_style = "BOX"
