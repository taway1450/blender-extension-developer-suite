"""Feature test: the editor members `area`, `region` and `space_data` read by code Blender calls while it draws an
editor, where nothing in the class names the editor: the `poll` of a Panel (whose `bl_space_type` comes from a mixin
listed after `Panel`) or a Menu, a tool's `draw_settings`, and `RenderEngine.view_update` / `view_draw` (the viewport
that shows the render). Blender fills them there in ordinary use, but a menu or a panel can be polled from a script or
`wm.call_menu`, so the checker takes them as not None and reports the read under blender-assumed-editor-member. An
operator's `execute` keeps the stub types. The assert_type calls are no-ops at runtime."""

from typing import assert_type

import bpy
from bpy.types import Area, Menu, Operator, Panel, Region, RenderEngine, Space, WorkSpaceTool

from . import draw


class AsmEditorMemberPanelMixin:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tool"


class ASM_EDITOR_MEMBER_PT_panel(Panel, AsmEditorMemberPanelMixin):
    bl_label = "Editor member"

    @classmethod
    def poll(cls, context):
        return context.region.type != 'TOOL_HEADER'  # ty: ignore[blender-assumed-editor-member]

    def draw(self, context):
        self.layout.label(text="Editor member")


class ASM_EDITOR_MEMBER_MT_menu(Menu):
    bl_label = "Editor member"

    @classmethod
    def poll(cls, context):
        assert_type(context.space_data, Space)  # ty: ignore[blender-assumed-editor-member]
        assert_type(context.area, Area)  # ty: ignore[blender-assumed-editor-member]
        if context.region is None:  # tested for None only: not reported
            return False
        return True

    def draw(self, context):
        self.layout.label(text="Editor member")


class ASM_EDITOR_MEMBER_RenderEngine(RenderEngine):
    bl_idname = "ASM_EDITOR_MEMBER"
    bl_label = "Editor member"

    def view_update(self, context, depsgraph):
        region = context.region  # ty: ignore[blender-assumed-editor-member]
        assert_type(region, Region)
        print(region.width, region.height)

    def view_draw(self, context, depsgraph):
        print(bpy.context.region.width)  # ty: ignore[blender-assumed-editor-member]

    def render(self, depsgraph):
        print(bpy.context.region.width)  # ty: ignore[missing-union-attribute]  # bare-ok: a final render runs in no editor


class AsmEditorMemberTool(WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = "asm_editor_member.tool"
    bl_label = "Editor member"

    def draw_settings(context, layout, tool):
        if bpy.context.region.type == 'TOOL_HEADER':  # ty: ignore[blender-assumed-editor-member]
            layout.label(text="Header")


class ASM_EDITOR_MEMBER_OT_run(Operator):
    bl_idname = "asm_editor_member.run"
    bl_label = "Run"

    def execute(self, context):
        assert_type(context.region, Region | None)  # bare-ok: an operator runs from any editor, or none
        return {'FINISHED'}


class ASM_EDITOR_MEMBER_OT_outline(Operator):
    bl_idname = "asm_editor_member.outline"
    bl_label = "Outline"

    _handle = None

    def invoke(self, context, event):
        self._handle = bpy.types.SpaceNodeEditor.draw_handler_add(
            draw.draw_outline, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        bpy.types.SpaceNodeEditor.draw_handler_remove(self._handle, 'WINDOW')
        return {'FINISHED'}


classes = (ASM_EDITOR_MEMBER_PT_panel, ASM_EDITOR_MEMBER_MT_menu, ASM_EDITOR_MEMBER_RenderEngine,
           ASM_EDITOR_MEMBER_OT_run, ASM_EDITOR_MEMBER_OT_outline)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.utils.register_tool(AsmEditorMemberTool)


def unregister():
    bpy.utils.unregister_tool(AsmEditorMemberTool)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
