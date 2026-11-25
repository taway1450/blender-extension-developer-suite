"""The measure operator: click two points in the 3D viewport."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty
from bpy.types import Operator
from bpy_extras import view3d_utils
from mathutils import Vector

from . import overlay


class VIEW3D_OT_viewport_tools_measure(Operator):
    """Click two points to measure the distance between them"""

    bl_idname = "view3d.viewport_tools_measure"
    bl_label = "Measure Distance"
    bl_options = {"REGISTER"}

    snap: BoolProperty(
        name="Snap", description="Round the points to whole units", default=False
    )

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == "VIEW_3D"

    def invoke(self, context, event):
        overlay.points.clear()
        overlay.add_handler()
        context.window_manager.modal_handler_add(self)
        # demo: blender-narrowed-by-poll
        context.area.tag_redraw()
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        # Blender polls before `invoke`, not before each `modal` call, so nothing says the editor is
        # still there. A modal operator of a viewport is written as if it were.
        # demo: later/editor-members-in-modal
        context.area.tag_redraw()
        if event.type in {"RIGHTMOUSE", "ESC"}:
            overlay.points.clear()
            return {"CANCELLED"}
        if event.type != "LEFTMOUSE" or event.value != "PRESS":
            return {"PASS_THROUGH"}

        # demo: later/editor-members-in-modal
        point = view3d_utils.region_2d_to_location_3d(
            context.region,
            context.space_data.region_3d,
            (event.mouse_region_x, event.mouse_region_y),
            context.scene.cursor.location,
        )
        if self.snap:
            point = Vector([round(value) for value in point])
        overlay.points.append(point)
        if len(overlay.points) < 2:
            return {"RUNNING_MODAL"}

        first, second = overlay.points
        self.report({"INFO"}, f"Distance: {(second - first).length:.3f}")
        return {"FINISHED"}


class VIEW3D_OT_viewport_tools_mark(Operator):
    """Add an empty at each measured point"""

    bl_idname = "view3d.viewport_tools_mark"
    bl_label = "Mark Measured Points"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(overlay.points) and context.mode == "OBJECT"

    def execute(self, context):
        for index, point in enumerate(overlay.points):
            bpy.ops.object.empty_add(type="PLAIN_AXES", location=point)
            # The operator makes the object it adds the active one.
            # demo: blender-assumed-added-object
            context.object.name = f"Measure {index + 1}"
        return {"FINISHED"}


classes = (VIEW3D_OT_viewport_tools_measure, VIEW3D_OT_viewport_tools_mark)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
