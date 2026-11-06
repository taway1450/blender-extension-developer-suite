"""Feature test: Blender fills preferences, window_manager, blend_data, scene, view_layer and tool_settings of the
context whenever it calls a callback, in background mode too. Reached through the context parameter, a renamed one,
bpy.context or an alias, they are never None there. The assert_type calls in the bodies are no-ops at runtime; the
operator also reports at runtime whether the members are set (_expected/runtime.toml)."""

from typing import assert_type

import bpy
from bpy.types import (BlendData, Context, Menu, Operator, Panel, Preferences, Scene, ToolSettings, UIList, ViewLayer,
                       WindowManager)


def members_set(context):
    """Whether every guaranteed member of ``context`` is set."""
    names = ("preferences", "window_manager", "blend_data", "scene", "view_layer", "tool_settings")
    return all(getattr(context, name) is not None for name in names)


class CTX_MEMBERS_PT_panel(Panel):
    bl_label = "Context Members"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    @classmethod
    def poll(cls, context):
        assert_type(context.scene, Scene)
        return True

    def draw(self, context):
        assert_type(context.preferences, Preferences)
        assert_type(context.window_manager, WindowManager)
        assert_type(context.blend_data, BlendData)
        assert_type(context.scene, Scene)
        assert_type(context.view_layer, ViewLayer)
        assert_type(context.tool_settings, ToolSettings)
        assert_type(bpy.context.scene, Scene)  # the same context as the parameter
        scene = context.scene
        assert_type(scene, Scene)
        assert_type([context.scene for _ in range(2)], list[Scene])  # a comprehension in the callback


class CTX_MEMBERS_OT_run(Operator):
    bl_idname = "ctx_members.run"
    bl_label = "Context Members"

    def execute(self, context):
        assert_type(context.preferences, Preferences)
        assert_type(context.window_manager, WindowManager)
        assert_type(context.blend_data, BlendData)
        assert_type(context.scene, Scene)
        assert_type(context.view_layer, ViewLayer)
        assert_type(context.tool_settings, ToolSettings)
        return {"FINISHED"} if members_set(context) else {"CANCELLED"}

    def invoke(self, ctx, event):
        assert_type(ctx.scene, Scene)  # a renamed context parameter
        return self.execute(ctx)


class CTX_MEMBERS_MT_menu(Menu):
    bl_label = "Context Members"

    def draw(self, context):
        assert_type(context.preferences, Preferences)
        assert_type(context.window_manager, WindowManager)
        assert_type(context.blend_data, BlendData)
        assert_type(context.scene, Scene)
        assert_type(context.view_layer, ViewLayer)
        assert_type(context.tool_settings, ToolSettings)


class CTX_MEMBERS_UL_list(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index, flt_flag):
        assert_type(context.preferences, Preferences)
        assert_type(context.window_manager, WindowManager)
        assert_type(context.blend_data, BlendData)
        assert_type(context.scene, Scene)
        assert_type(context.view_layer, ViewLayer)
        assert_type(context.tool_settings, ToolSettings)

        def later(other: Context) -> None:
            assert_type(other.scene, Scene | None)  # bare-ok: a nested function may run after the callback returns


classes = (CTX_MEMBERS_PT_panel, CTX_MEMBERS_OT_run, CTX_MEMBERS_MT_menu, CTX_MEMBERS_UL_list)
register, unregister = bpy.utils.register_classes_factory(classes)
