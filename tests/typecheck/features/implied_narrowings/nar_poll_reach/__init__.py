"""Feature test: what a poll() checked reaches further than the callbacks of its own class.

- Blender polls a sub-panel only while it draws the parent panel, which it draws only after the parent's poll() returned
  True (ed_panel_draw in area.cc). So the polls up the bl_parent_id chain hold in a sub-panel's own poll() and in the
  callbacks it gates, reported under blender-narrowed-by-poll with the parent named. A sub-panel the add-on also opens
  as a popover is drawn without its parent, so it gets nothing.
- A read inside poll() itself knows what the poll's earlier guards checked, helpers included: plain control flow, not
  reported.
- getattr(context, "x", None) and (ob := context.x) are the path context.x; XrSessionState.is_running(context) checks
  window_manager.xr_session_state; bool(a and b) checks a and b; a helper's try body counts when its except returns
  False. A helper passed a member of the context (`helpers.is_mesh(context.object)`) checks that member.

The assert_type calls in the bodies are no-ops at runtime."""

from typing import assert_type

import bpy
from bpy.types import Material, Mesh, Object, Operator, Panel, XrSessionState

from . import helpers
from .sub_panels import NAR_REACH_PT_far


class NAR_REACH_PT_parent(Panel):
    bl_label = "Parent"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Reach"

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw(self, context):
        self.layout.popover("NAR_REACH_PT_popover_child")


class NAR_REACH_PT_child(Panel):
    bl_label = "Child"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Reach"
    bl_parent_id = "NAR_REACH_PT_parent"

    @classmethod
    def poll(cls, context):
        ob = context.object  # ty: ignore[blender-narrowed-by-poll]
        assert_type(ob, Object)
        return ob.active_material is not None

    def draw(self, context):
        assert_type(context.object, Object)  # ty: ignore[blender-narrowed-by-poll]
        assert_type(context.object.active_material, Material)  # ty: ignore[blender-narrowed-by-poll]
        assert_type(context.material, Material | None)  # bare-ok: no poll up the chain checked it
        context.scene.camera.name  # ty: ignore[missing-union-attribute]  # bare-ok: no poll checked scene.camera


class NarReachGrandchild(Panel):
    bl_idname = "NAR_REACH_PT_grandchild"
    bl_label = "Grandchild"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Reach"
    bl_parent_id = "NAR_REACH_PT_child"

    def draw(self, context):
        assert_type(context.object.active_material, Material)  # ty: ignore[blender-narrowed-by-poll]


class NAR_REACH_PT_popover_child(Panel):
    bl_label = "Popover child"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Reach"
    bl_parent_id = "NAR_REACH_PT_parent"

    def draw(self, context):
        context.object.name  # ty: ignore[missing-union-attribute]  # bare-ok: a popover is drawn without its parent


class NAR_REACH_OT_flow(Operator):
    bl_idname = "nar_reach.flow"
    bl_label = "Flow"

    @classmethod
    def poll(cls, context):
        if not helpers.has_object(context):
            return False
        assert_type(context.object, Object)  # oracle-skip: narrowed by the poll's own guard, silently
        assert_type(context.material, Material | None)  # bare-ok: the guard did not check it
        return context.object.mode == "OBJECT"

    def execute(self, context):
        assert_type(context.object, Object)  # ty: ignore[blender-narrowed-by-poll]
        return {"FINISHED"}


class NAR_REACH_OT_flow_and(Operator):
    bl_idname = "nar_reach.flow_and"
    bl_label = "Flow through and"

    @classmethod
    def poll(cls, context):
        return helpers.has_object(context) and assert_type(context.object, Object).mode == "EDIT"  # oracle-skip: silent

    def execute(self, context):
        return {"FINISHED"}


class NAR_REACH_PT_getattr(Panel):
    bl_label = "getattr"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Reach"

    @classmethod
    def poll(cls, context):
        ob = getattr(context, "object", None)
        return ob is not None and getattr(context, "material", None) is not None

    def draw(self, context):
        assert_type(context.object, Object)  # ty: ignore[blender-narrowed-by-poll]
        assert_type(context.material, Material)  # ty: ignore[blender-narrowed-by-poll]


class NAR_REACH_PT_walrus(Panel):
    bl_label = "Walrus"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Reach"

    @classmethod
    def poll(cls, context):
        if (material := context.material) is None:
            return False
        return material.users > 0 and (ob := context.active_object) is not None and ob.active_material is not None

    def draw(self, context):
        assert_type(context.material, Material)  # ty: ignore[blender-narrowed-by-poll]
        assert_type(context.active_object.active_material, Material)  # ty: ignore[blender-narrowed-by-poll]


class NAR_REACH_PT_xr(Panel):
    bl_label = "VR"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Reach"

    @classmethod
    def poll(cls, context):
        return bpy.types.XrSessionState.is_running(context)

    def draw(self, context):
        assert_type(context.window_manager.xr_session_state, XrSessionState)  # ty: ignore[blender-narrowed-by-poll]


class NAR_REACH_OT_xr(Operator):
    bl_idname = "nar_reach.xr"
    bl_label = "VR"

    @classmethod
    def poll(cls, context):
        return XrSessionState.is_running(context)

    def execute(self, context):
        context.window_manager.xr_session_state.navigation_scale  # ty: ignore[blender-narrowed-by-poll]
        return {"FINISHED"}


class NAR_REACH_PT_bool(Panel):
    bl_label = "bool"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Reach"

    @classmethod
    def poll(cls, context):
        return bool(context.object and context.object.active_material)

    def draw(self, context):
        assert_type(context.object.active_material, Material)  # ty: ignore[blender-narrowed-by-poll]


class NAR_REACH_PT_try(Panel):
    bl_label = "try"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Reach"

    @classmethod
    def poll(cls, context):
        return helpers.has_material(context)

    def draw(self, context):
        assert_type(context.object.active_material, Material)  # ty: ignore[blender-narrowed-by-poll]


class NAR_REACH_PT_member_helper(Panel):
    bl_label = "member helper"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Reach"

    @classmethod
    def poll(cls, context):
        return helpers.is_mesh(context.object)

    def draw(self, context):
        assert_type(context.object.data, Mesh)  # ty: ignore[blender-narrowed-by-poll]


classes = (NAR_REACH_PT_parent, NAR_REACH_PT_child, NarReachGrandchild, NAR_REACH_PT_popover_child, NAR_REACH_PT_far,
           NAR_REACH_OT_flow, NAR_REACH_OT_flow_and, NAR_REACH_PT_getattr, NAR_REACH_PT_walrus, NAR_REACH_PT_xr,
           NAR_REACH_OT_xr, NAR_REACH_PT_bool, NAR_REACH_PT_try, NAR_REACH_PT_member_helper)
register, unregister = bpy.utils.register_classes_factory(classes)
