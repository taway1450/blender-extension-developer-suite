"""Hover shows the editor's Space subclass a menu's idname prefix gives context.space_data."""

from bpy.types import Menu


class CLIP_MT_nar_menu_prefix_hover(Menu):
    def draw(self, context):
        context.space_data
        #       ^hover-contains "SpaceClipEditor"
