"""Feature test: Blender passes UIList.draw_item an `item` that is None only for an empty slot of an array of ID
pointers, which a list of an add-on's collection never has. An unannotated `item` (also in an override of an
unannotated override) is taken as not None and its reads are reported under blender-assumed-list-item; a read only
tested for truth or None is not. Where the add-on draws the list with `template_list("<list>", ..., dataptr,
"propname")` (in any of its modules, here panels.py), Blender passes `item` from that collection, so it is typed as
the collection's element type, the union of them when the list shows several collections. It passes `dataptr` as
`data` to draw_item and filter_items, so `data` is typed as `dataptr`, likewise. The assert_type calls are no-ops at
runtime."""

from typing import assert_type

import bpy
from bpy.props import CollectionProperty, IntProperty, StringProperty
from bpy.types import MaterialSlot, Object, PropertyGroup, Scene, UIList, VertexGroup, bpy_struct

from . import panels


class ASM_LIST_ITEM_Entry(PropertyGroup):
    label: StringProperty()


class AsmListItemBase(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=str(index))


class ASM_LIST_ITEM_UL_entries(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        assert_type(item, bpy_struct)  # ty: ignore[blender-assumed-list-item]
        layout.prop(item, "name", text="", emboss=False)  # ty: ignore[blender-assumed-list-item]


class ASM_LIST_ITEM_UL_tested(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if item is None:  # tested for None only: not reported
            return
        layout.label(text=str(index))


class ASM_LIST_ITEM_UL_derived(AsmListItemBase):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "name")  # ty: ignore[blender-assumed-list-item]


class ASM_LIST_ITEM_UL_sourced(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        assert_type(item, ASM_LIST_ITEM_Entry)  # ty: ignore[blender-assumed-list-item]
        assert_type(data, Scene)
        layout.label(text=item.label)  # ty: ignore[blender-assumed-list-item]
        layout.label(text=item.lable)  # ty: ignore[blender-assumed-list-item, missing-attribute]

    def filter_items(self, context, data, propname):
        assert_type(data, Scene)
        return [], []


class ASM_LIST_ITEM_UL_slots(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        assert_type(item, MaterialSlot)  # ty: ignore[blender-assumed-list-item]
        assert_type(data, Object)
        slot = item  # ty: ignore[blender-assumed-list-item]
        if slot.material:
            layout.prop(slot.material, "name", text="", emboss=False)


class ASM_LIST_ITEM_UL_two_sources(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        assert_type(item, ASM_LIST_ITEM_Entry | VertexGroup)  # ty: ignore[blender-assumed-list-item]
        assert_type(data, Scene | Object)
        layout.label(text=item.name)  # ty: ignore[blender-assumed-list-item]


class ASM_LIST_ITEM_UL_unknown_source(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        assert_type(item, bpy_struct)  # ty: ignore[blender-assumed-list-item]
        assert_type(data, bpy_struct)  # bare-ok: no call with a typed `dataptr` names the list


class ASM_LIST_ITEM_UL_annotated(UIList):
    def draw_item(self, context, layout, data, item: bpy_struct | None, icon, active_data, active_propname, index):
        layout.prop(item, "name")  # ty: ignore[invalid-argument-type]  # bare-ok: an annotation with None keeps None


classes = (ASM_LIST_ITEM_Entry, ASM_LIST_ITEM_UL_entries, ASM_LIST_ITEM_UL_tested, ASM_LIST_ITEM_UL_derived,
           ASM_LIST_ITEM_UL_sourced, ASM_LIST_ITEM_UL_slots, ASM_LIST_ITEM_UL_two_sources,
           ASM_LIST_ITEM_UL_unknown_source, ASM_LIST_ITEM_UL_annotated, panels.ASM_LIST_ITEM_PT_lists)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.asm_list_item_entries = CollectionProperty(type=ASM_LIST_ITEM_Entry)
    bpy.types.Scene.asm_list_item_index = IntProperty()


def unregister():
    del bpy.types.Scene.asm_list_item_index
    del bpy.types.Scene.asm_list_item_entries
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
