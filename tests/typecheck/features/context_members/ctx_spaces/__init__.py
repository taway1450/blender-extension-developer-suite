"""Feature test: Blender draws a Panel or a Header, and runs a GizmoGroup, in an editor of its bl_space_type, so
area, space_data and region are set there and space_data is that editor's Space subclass. A Menu, a UIList and an
Operator have no bl_space_type: they run from any editor, or none. The assert_type calls in the bodies are no-ops at
runtime."""

from typing import assert_type

import bpy
from bpy.types import (Area, GizmoGroup, Header, Menu, Operator, Panel, Region, Space, SpaceImageEditor, SpaceProperties,
                       SpaceView3D, UIList)


class CTX_SPACES_PT_view3d(Panel):
    bl_label = "Context Spaces"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    @classmethod
    def poll(cls, context):
        assert_type(context.space_data, SpaceView3D)
        return True

    def draw(self, context):
        assert_type(context.space_data, SpaceView3D)
        assert_type(context.area, Area)
        assert_type(context.region, Region)
        space = context.space_data
        assert_type(space.shading, bpy.types.View3DShading)


class CtxSpacesImageMixin:
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"


class CTX_SPACES_PT_image(CtxSpacesImageMixin, Panel):
    bl_label = "Context Spaces"

    def draw(self, context):
        assert_type(context.space_data, SpaceImageEditor)  # bl_space_type from a base


class CTX_SPACES_HT_properties(Header):
    bl_space_type = "PROPERTIES"

    def draw(self, context):
        assert_type(context.space_data, SpaceProperties)
        assert_type(context.area, Area)
        assert_type(context.region, Region)


class CTX_SPACES_HT_topbar(Header):
    bl_space_type = "TOPBAR"

    def draw(self, context):
        assert_type(context.space_data, Space)  # the top bar has no Space subclass
        assert_type(context.area, Area)


class CTX_SPACES_GGT_gizmos(GizmoGroup):
    bl_label = "Context Spaces"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"

    def setup(self, context):
        assert_type(context.space_data, SpaceView3D)
        assert_type(context.area, Area)
        assert_type(context.region, Region)


class CTX_SPACES_MT_menu(Menu):
    bl_label = "Context Spaces"

    def draw(self, context):
        assert_type(context.space_data, Space | None)  # bare-ok: a menu opens from any editor
        assert_type(context.area, Area | None)  # bare-ok: a menu opens from any editor


class CTX_SPACES_UL_list(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index, flt_flag):
        assert_type(context.space_data, Space | None)  # bare-ok: a list is drawn in any layout


class CTX_SPACES_OT_run(Operator):
    bl_idname = "ctx_spaces.run"
    bl_label = "Context Spaces"

    def execute(self, context):
        assert_type(context.space_data, Space | None)  # bare-ok: an operator runs from anywhere, or in --background
        assert_type(context.area, Area | None)  # bare-ok: an operator runs from anywhere, or in --background
        assert_type(context.region, Region | None)  # bare-ok: an operator runs from anywhere, or in --background
        return {"FINISHED"} if context.space_data is None else {"CANCELLED"}


classes = (CTX_SPACES_PT_view3d, CTX_SPACES_PT_image, CTX_SPACES_HT_properties, CTX_SPACES_HT_topbar,
           CTX_SPACES_GGT_gizmos, CTX_SPACES_MT_menu, CTX_SPACES_UL_list, CTX_SPACES_OT_run)
register, unregister = bpy.utils.register_classes_factory(classes)
