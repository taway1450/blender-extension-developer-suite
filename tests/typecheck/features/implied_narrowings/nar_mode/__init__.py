"""Feature test: a poll() that checks context.mode narrows what the mode implies.

context.mode is computed from the edit object or else the active object (CTX_data_mode_enum_ex in context.cc):
- each EDIT_* mode means an object of that type is in edit mode, so context.object, active_object and edit_object are
  set, with that Type tag (EDIT_MESH: a mesh object);
- a paint or sculpt mode means the active object is in it, and entering it ensures its tool settings
  (BKE_paint_ensure): SCULPT gives tool_settings.sculpt, PAINT_VERTEX vertex_paint, PAINT_GREASE_PENCIL gpencil_paint,
  and so on;
- POSE means the active object is an armature in pose mode, whose pose is set.

Reported under blender-narrowed-by-poll in the callbacks the poll gates, like any other poll fact; in the poll's own
later reads it is silent.

The assert_type calls in the bodies are no-ops at runtime."""

from typing import assert_type

import bpy
from bpy.types import Mesh, Operator, Panel, Pose, Sculpt, VertexPaint


class NAR_MODE_OT_edit_mesh(Operator):
    bl_idname = "nar_mode.edit_mesh"
    bl_label = "Edit mesh"

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        assert_type(context.object.data, Mesh)  # ty: ignore[blender-narrowed-by-poll]
        assert_type(context.active_object.data, Mesh)  # ty: ignore[blender-narrowed-by-poll]
        assert_type(context.edit_object.data, Mesh)  # ty: ignore[blender-narrowed-by-poll]
        context.tool_settings.sculpt.brush  # ty: ignore[missing-union-attribute]  # bare-ok: edit mode has no sculpt settings
        return {"FINISHED"}


class NAR_MODE_PT_sculpt(Panel):
    bl_label = "Sculpt"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Mode"

    @classmethod
    def poll(cls, context):
        if context.mode != "SCULPT":
            return False
        assert_type(context.tool_settings.sculpt, Sculpt)  # oracle-skip: the poll's own guard, silent
        return True

    def draw(self, context):
        assert_type(context.tool_settings.sculpt, Sculpt)  # ty: ignore[blender-narrowed-by-poll]
        context.object.data.name  # ty: ignore[blender-narrowed-by-poll]


class NAR_MODE_PT_vertex_weight(Panel):
    bl_label = "Vertex or weight paint"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Mode"

    @classmethod
    def poll(cls, context):
        return context.mode in {"PAINT_VERTEX", "PAINT_WEIGHT"}

    def draw(self, context):
        assert_type(context.object.data, Mesh)  # ty: ignore[blender-narrowed-by-poll]
        context.tool_settings.vertex_paint.brush  # ty: ignore[missing-union-attribute]  # bare-ok: only one of the two modes
        assert_type(context.tool_settings.weight_paint, VertexPaint | None)  # bare-ok: only one of the two modes


class NAR_MODE_OT_pose(Operator):
    bl_idname = "nar_mode.pose"
    bl_label = "Pose"

    @classmethod
    def poll(cls, context):
        return context.mode == "POSE"

    def execute(self, context):
        assert_type(context.object.pose, Pose)  # ty: ignore[blender-narrowed-by-poll]
        assert_type(context.active_object.pose, Pose)  # ty: ignore[blender-narrowed-by-poll]
        return {"FINISHED"}


class NAR_MODE_OT_object(Operator):
    bl_idname = "nar_mode.object"
    bl_label = "Object mode"

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def execute(self, context):
        context.object.name  # ty: ignore[missing-union-attribute]  # bare-ok: object mode needs no object
        return {"FINISHED"}


classes = (NAR_MODE_OT_edit_mesh, NAR_MODE_PT_sculpt, NAR_MODE_PT_vertex_weight, NAR_MODE_OT_pose, NAR_MODE_OT_object)
register, unregister = bpy.utils.register_classes_factory(classes)
