"""A gizmo in the 3D viewport that changes the energy of the active light, and a button that measures."""

from __future__ import annotations

import bpy
from bpy.types import GizmoGroup


class VIEWPORT_TOOLS_GGT_light(GizmoGroup):
    bl_idname = "VIEWPORT_TOOLS_GGT_light"
    bl_label = "Light Energy"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_options = {"3D", "PERSISTENT"}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob is not None and ob.type == "LIGHT"

    def setup(self, context):
        # demo: blender-narrowed-by-poll
        light = context.object.data
        arrow = self.gizmos.new("GIZMO_GT_arrow_3d")
        arrow.target_set_prop("offset", light, "energy")
        # A built-in gizmo type has properties of its own, which `gizmos.new()` does not give.
        # demo: later/builtin-gizmo-types
        arrow.draw_style = "BOX"
        arrow.color = 1.0, 0.5, 0.0
        arrow.alpha = 0.5
        arrow.color_highlight = 1.0, 0.5, 1.0
        arrow.scale_basis = 1.5
        self.energy_gizmo = arrow

        button = self.gizmos.new("GIZMO_GT_button_2d")
        button.icon = "DRIVER_DISTANCE"
        button.draw_options = {"BACKDROP", "OUTLINE"}
        button.scale_basis = 0.2
        # demo: operator_properties
        props = button.target_set_operator("view3d.viewport_tools_measure")
        props.snap = True
        self.measure_gizmo = button

    def refresh(self, context):
        matrix = context.object.matrix_world.normalized()
        self.energy_gizmo.matrix_basis = matrix
        self.measure_gizmo.matrix_basis = matrix


def register():
    bpy.utils.register_class(VIEWPORT_TOOLS_GGT_light)


def unregister():
    bpy.utils.unregister_class(VIEWPORT_TOOLS_GGT_light)
