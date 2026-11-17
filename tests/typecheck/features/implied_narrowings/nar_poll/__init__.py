"""Feature test: Blender calls a Panel's draw callbacks, a Menu's draw, an Operator's invoke and execute and a
GizmoGroup's setup callbacks only after the class's poll() returned True, with the same context. A pointer that poll()
checked is therefore not None there: the checker accepts the read and reports it under blender-narrowed-by-poll. A
pointer poll() did not check stays an error. The assert_type calls in the bodies are no-ops at runtime."""

from typing import assert_type

import bpy
from bpy.types import (Area, EditBone, GizmoGroup, Light, Material, Menu, Mesh, Node, NodeTree, Object, Operator, Panel,
                       PoseBone, SpaceNodeEditor, SpaceProperties, SpaceView3D)

from . import helpers


class NAR_POLL_PT_conjuncts(Panel):
    bl_label = "Conjuncts"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        return (
            context.object is not None
            and context.active_node
            and isinstance(context.edit_bone, EditBone)
            and bool(context.pose_bone)
            and bpy.context.edit_object is not None
            and context.object.active_material is not None
        )

    def draw(self, context):
        assert_type(context.object, Object)  # ty: ignore[blender-narrowed-by-poll]
        assert_type(context.active_node, Node)  # ty: ignore[blender-narrowed-by-poll]
        assert_type(context.edit_bone, EditBone)  # ty: ignore[blender-narrowed-by-poll]
        assert_type(context.pose_bone, PoseBone)  # ty: ignore[blender-narrowed-by-poll]
        assert_type(bpy.context.edit_object, Object)  # ty: ignore[blender-narrowed-by-poll]
        self.layout.prop(context.object, "name")  # ty: ignore[blender-narrowed-by-poll]
        ob = context.object  # ty: ignore[blender-narrowed-by-poll]
        assert_type(ob.active_material, Material)  # ty: ignore[blender-narrowed-by-poll]
        assert_type(context.material, Material | None)  # bare-ok: the poll did not check it
        context.scene.camera.name  # ty: ignore[missing-union-attribute]  # bare-ok: the poll did not check scene.camera

    def draw_header(self, context):
        assert_type(context.pose_bone, PoseBone)  # ty: ignore[blender-narrowed-by-poll]


class NAR_POLL_PT_guards(Panel):
    bl_label = "Guards"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        if ob is None:
            return False
        if ob.type != "MESH":
            return False
        if not context.material or context.material.node_tree is None:
            return False
        return True

    def draw(self, context):
        assert_type(context.active_object.data, Mesh)  # ty: ignore[blender-narrowed-by-poll]
        assert_type(context.material, Material)  # ty: ignore[blender-narrowed-by-poll]
        if context.material:  # tested for truth only: not reported
            self.layout.label(text=context.material.name)
        material = context.material
        if material is None:  # the callback tests the path itself: not reported
            return
        self.layout.label(text=material.name)


class NarPollObjectMixin:
    @classmethod
    def poll(cls, context):
        return context.object is not None


class NAR_POLL_PT_mixin(NarPollObjectMixin, Panel):
    bl_label = "Mixin"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    def draw(self, context):
        assert_type(context.object, Object)  # ty: ignore[blender-narrowed-by-poll]


class NAR_POLL_PT_super(NarPollObjectMixin, Panel):
    bl_label = "Super"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"

    @classmethod
    def poll(cls, context):
        return super().poll(context) and context.material is not None

    def draw(self, context):
        assert_type(context.object, Object)  # ty: ignore[blender-narrowed-by-poll]
        assert_type(context.material, Material)  # ty: ignore[blender-narrowed-by-poll]


class NAR_POLL_OT_helpers(Operator):
    bl_idname = "nar_poll.helpers"
    bl_label = "Helpers"

    @classmethod
    def poll(cls, context):
        return NarPollObjectMixin.poll(context) and helpers.in_node_editor(context)

    def invoke(self, context, event):
        assert_type(context.object, Object)  # ty: ignore[blender-narrowed-by-poll]
        return self.execute(context)

    def execute(self, context):
        assert_type(context.space_data, SpaceNodeEditor)  # ty: ignore[blender-narrowed-by-poll]
        assert_type(context.space_data.edit_tree, NodeTree)  # ty: ignore[blender-narrowed-by-poll]
        return {"FINISHED"}

    def modal(self, context, event):
        assert_type(context.object, Object | None)  # bare-ok: modal runs on later events, without a new poll
        return {"FINISHED"}

    def draw(self, context):
        assert_type(context.object, Object | None)  # bare-ok: a props dialog draws without a new poll


class NAR_POLL_MT_area(Menu):
    bl_label = "Area"

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == "VIEW_3D"

    def draw(self, context):
        assert_type(context.area, Area)  # ty: ignore[blender-narrowed-by-poll]
        assert_type(context.space_data, SpaceView3D)  # ty: ignore[blender-narrowed-by-poll]


class NAR_POLL_GGT_light(GizmoGroup):
    bl_label = "Light"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob and ob.type == "LIGHT"

    def setup(self, context):
        assert_type(context.object.data, Light)  # ty: ignore[blender-narrowed-by-poll]


class NAR_POLL_PT_no_poll(Panel):
    bl_label = "No poll"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    def draw(self, context):
        assert_type(context.object, Object | None)  # bare-ok: no poll checked it
        assert_type(context.space_data, SpaceProperties)


classes = (NAR_POLL_PT_conjuncts, NAR_POLL_PT_guards, NAR_POLL_PT_mixin, NAR_POLL_PT_super, NAR_POLL_OT_helpers,
           NAR_POLL_MT_area, NAR_POLL_GGT_light, NAR_POLL_PT_no_poll)
register, unregister = bpy.utils.register_classes_factory(classes)
