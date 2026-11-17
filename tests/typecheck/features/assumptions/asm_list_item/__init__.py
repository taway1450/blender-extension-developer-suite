"""Feature test: Blender passes UIList.draw_item an `item` that is None only for an empty slot of an array of ID
pointers, which a list of an add-on's collection never has. An unannotated `item` (also in an override of an
unannotated override) is taken as not None and its reads are reported under blender-assumed-list-item; a read only
tested for truth or None is not. The assert_type calls are no-ops at runtime."""

from typing import assert_type

import bpy
from bpy.props import CollectionProperty, IntProperty, StringProperty
from bpy.types import PropertyGroup, UIList, bpy_struct


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


class ASM_LIST_ITEM_UL_annotated(UIList):
    def draw_item(self, context, layout, data, item: bpy_struct | None, icon, active_data, active_propname, index):
        layout.prop(item, "name")  # ty: ignore[invalid-argument-type]  # bare-ok: an annotation with None keeps None


classes = (ASM_LIST_ITEM_Entry, ASM_LIST_ITEM_UL_entries, ASM_LIST_ITEM_UL_tested, ASM_LIST_ITEM_UL_derived,
           ASM_LIST_ITEM_UL_annotated)


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
