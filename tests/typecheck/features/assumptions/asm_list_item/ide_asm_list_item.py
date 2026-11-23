"""Hover shows the type an assumed list item is narrowed to: its source's element type where a `template_list` call
names the list."""

from bpy.types import Object, UILayout, UIList


class ASM_LIST_ITEM_UL_hover(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        item
        #   ^hover


class ASM_LIST_ITEM_UL_hover_sourced(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        item
        #   ^hover


def draw_hover_list(layout: UILayout, ob: Object) -> None:
    layout.template_list("ASM_LIST_ITEM_UL_hover_sourced", "", ob, "material_slots", ob, "active_material_index")
