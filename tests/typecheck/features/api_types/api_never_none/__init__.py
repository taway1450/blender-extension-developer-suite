"""Feature test: Blender always passes a context to these callbacks, except RenderEngine.view_draw, which gets None
when a viewport is drawn off-screen (Viewport Render, GPUOffScreen.draw_view3d). It also always fills UIList.draw_item's
data, KeyingSetInfo's keying set, AssetShelf's asset and layout and RenderEngine's depsgraph; draw_item's item and
active_data can be None. The unannotated overrides take the parameter types of the stubs, so the stubs must state it.
The assert_type calls in the bodies are no-ops at runtime."""

from typing import assert_type

import bpy
from bpy.types import (AssetRepresentation, AssetShelf, Context, Depsgraph, Header, KeyingSet, KeyingSetInfo, Menu,
                       RenderEngine, UILayout, UIList, bpy_struct)


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
        assert_type(data, bpy_struct)
        assert_type(item, bpy_struct)  # ty: ignore[blender-assumed-list-item]  # None only for an empty slot of an ID-pointer array
        assert_type(active_data, bpy_struct | None)

    def draw_filter(self, context, layout):
        assert_type(context, Context)


class API_NEVER_NONE_Engine(RenderEngine):
    bl_idname = "API_NEVER_NONE"
    bl_label = "Never None"

    def update(self, data, depsgraph):
        assert_type(depsgraph, Depsgraph)

    def render(self, depsgraph):
        assert_type(depsgraph, Depsgraph)

    def bake(self, depsgraph, object, pass_type, pass_filter, width, height):
        assert_type(depsgraph, Depsgraph)

    def view_update(self, context, depsgraph):
        assert_type(context, Context)
        assert_type(depsgraph, Depsgraph)

    def view_draw(self, context, depsgraph):
        assert_type(context, Context | None)  # None when drawn off-screen
        assert_type(depsgraph, Depsgraph)


class API_NEVER_NONE_KSI_keying_set(KeyingSetInfo):
    bl_idname = "API_NEVER_NONE_KSI_keying_set"
    bl_label = "Never None"

    def poll(self, context):
        return True

    def iterator(self, context, ks):
        assert_type(ks, KeyingSet)

    def generate(self, context, ks, data):
        assert_type(ks, KeyingSet)


class API_NEVER_NONE_AST_shelf(AssetShelf):
    bl_idname = "API_NEVER_NONE_AST_shelf"
    bl_space_type = "VIEW_3D"

    @classmethod
    def asset_poll(cls, asset):
        assert_type(asset, AssetRepresentation)
        return True

    @classmethod
    def draw_context_menu(cls, context, asset, layout):
        assert_type(asset, AssetRepresentation)
        assert_type(layout, UILayout)


classes = (API_NEVER_NONE_MT_menu, API_NEVER_NONE_HT_header, API_NEVER_NONE_UL_list, API_NEVER_NONE_Engine,
           API_NEVER_NONE_KSI_keying_set, API_NEVER_NONE_AST_shelf)
register, unregister = bpy.utils.register_classes_factory(classes)
