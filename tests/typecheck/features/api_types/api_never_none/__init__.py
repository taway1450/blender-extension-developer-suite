"""Feature test: Blender always passes a context to these callbacks, except RenderEngine.view_draw, which gets None
when a viewport is drawn off-screen (Viewport Render, GPUOffScreen.draw_view3d). The unannotated overrides take the
parameter types of the stubs, so the stubs must state it. The assert_type calls in the bodies are no-ops at runtime."""

from typing import assert_type

import bpy
from bpy.types import Context, Header, Menu, RenderEngine, UIList


class API_NEVER_NONE_MT_menu(Menu):
    bl_label = "Never None"

    @classmethod
    def poll(cls, context):
        assert_type(context, Context)
        return True

    def draw(self, context):
        assert_type(context, Context)


class API_NEVER_NONE_HT_header(Header):
    bl_space_type = "VIEW_3D"

    def draw(self, context):
        assert_type(context, Context)


class API_NEVER_NONE_UL_list(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index, flt_flag):
        assert_type(context, Context)

    def draw_filter(self, context, layout):
        assert_type(context, Context)


class API_NEVER_NONE_Engine(RenderEngine):
    bl_idname = "API_NEVER_NONE"
    bl_label = "Never None"

    def view_update(self, context, depsgraph):
        assert_type(context, Context)

    def view_draw(self, context, depsgraph):
        assert_type(context, Context | None)  # None when drawn off-screen


classes = (API_NEVER_NONE_MT_menu, API_NEVER_NONE_HT_header, API_NEVER_NONE_UL_list, API_NEVER_NONE_Engine)
register, unregister = bpy.utils.register_classes_factory(classes)
