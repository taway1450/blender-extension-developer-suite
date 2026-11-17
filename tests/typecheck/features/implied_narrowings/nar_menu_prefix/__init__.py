"""Feature test: a Menu has no bl_space_type, but by Blender's convention its idname starts with the header prefix of
the editor it is drawn in (CLIP_MT_view is drawn in the clip editor, whose header is CLIP_HT_header). In a menu's draw
and poll the checker types context.space_data as that editor's Space subclass and context.area as not None, and
reports the read under blender-narrowed-by-menu-prefix: wm.call_menu can draw any menu anywhere. The assert_type calls
in the bodies are no-ops at runtime."""

from typing import assert_type

import bpy
from bpy.types import Area, Context, Menu, Space, SpaceClipEditor, SpaceDopeSheetEditor, SpaceView3D


class VIEW3D_MT_nar_menu_prefix(Menu):
    bl_label = "Menu prefix"

    @classmethod
    def poll(cls, context):
        assert_type(context.space_data, SpaceView3D)  # ty: ignore[blender-narrowed-by-menu-prefix]
        return True

    def draw(self, context):
        assert_type(context.space_data, SpaceView3D)  # ty: ignore[blender-narrowed-by-menu-prefix]
        assert_type(context.area, Area)  # ty: ignore[blender-narrowed-by-menu-prefix]
        self.layout.prop(context.space_data, "show_gizmo")  # ty: ignore[blender-narrowed-by-menu-prefix]
        self.draw_helper(context)

    def draw_helper(self, context: Context):
        assert_type(context.space_data, Space | None)  # bare-ok: Blender does not call a helper method itself


class NarMenuPrefixClip(Menu):
    bl_idname = "CLIP_MT_nar_menu_prefix"
    bl_label = "Menu prefix"

    def draw(self, context):
        space = context.space_data  # ty: ignore[blender-narrowed-by-menu-prefix]
        assert_type(space.clip, bpy.types.MovieClip | None)


class TIME_MT_nar_menu_prefix(Menu):
    bl_label = "Menu prefix"

    def draw(self, context):
        assert_type(context.space_data, SpaceDopeSheetEditor)  # ty: ignore[blender-narrowed-by-menu-prefix]


class TOPBAR_MT_nar_menu_prefix(Menu):
    bl_label = "Menu prefix"

    def draw(self, context):
        assert_type(context.space_data, Space)  # ty: ignore[blender-narrowed-by-menu-prefix]


class NAR_MENU_PREFIX_MT_own(Menu):
    bl_label = "Menu prefix"

    def draw(self, context):
        assert_type(context.space_data, Space | None)  # bare-ok: an add-on's own prefix names no editor
        assert_type(context.area, Area | None)  # bare-ok: an add-on's own prefix names no editor


classes = (VIEW3D_MT_nar_menu_prefix, NarMenuPrefixClip, TIME_MT_nar_menu_prefix, TOPBAR_MT_nar_menu_prefix,
           NAR_MENU_PREFIX_MT_own)
register, unregister = bpy.utils.register_classes_factory(classes)
