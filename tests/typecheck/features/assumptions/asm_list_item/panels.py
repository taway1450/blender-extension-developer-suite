"""The panel that draws the add-on's lists: each `template_list` call names a list and the collection it shows."""

from bpy.types import Panel


class ASM_LIST_ITEM_PT_lists(Panel):
    bl_label = "Lists"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.template_list("ASM_LIST_ITEM_UL_sourced", "", scene, "asm_list_item_entries",
                             scene, "asm_list_item_index")
        layout.template_list("ASM_LIST_ITEM_UL_two_sources", "entries", scene, "asm_list_item_entries",
                             scene, "asm_list_item_index")
        ob = context.object
        if ob is None:
            return
        layout.template_list("ASM_LIST_ITEM_UL_slots", "", ob, "material_slots", ob, "active_material_index")
        layout.template_list("ASM_LIST_ITEM_UL_two_sources", "groups", ob, "vertex_groups",
                             scene, "asm_list_item_index")
        draw_list(layout, ob)


def draw_list(layout, data):
    # `data` is unannotated, so these calls say nothing: the slots list keeps the type its other call gives, and the
    # list with no other call keeps `bpy_struct`.
    layout.template_list("ASM_LIST_ITEM_UL_unknown_source", "", data, "material_slots", data, "active_material_index")
    layout.template_list("ASM_LIST_ITEM_UL_slots", "", data, "material_slots", data, "active_material_index")
