"""Hover shows the type an assumed list item is narrowed to."""

from bpy.types import UIList


class ASM_LIST_ITEM_UL_hover(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        item
        #   ^hover
