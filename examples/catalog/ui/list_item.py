# /// catalog
# title = "`template_list` and a `UIList`"
# section = "lists"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["assumptions"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs type `draw_item`'s `data` and `item` as `AnyType` and `layout` as `UILayout | None`, which the checker does not narrow."
# "fake-bpy-module/5.2" = "These stubs type the callbacks' `context` and `layout` with `| None`, so their reads are reported."
# ///
"""`layout.template_list` draws a collection as a list, one row per item through the `UIList`'s `draw_item`. The
checker reads which collection the add-on gives the list and types `item` as its element type and `data` as the
collection's owner. The stubs allow `None` for `item`; the checker takes it as set, since an add-on's own collection
has no empty items, and reports the read as an Assumption."""

# catalog: hide
from typing import assert_type

# catalog: show
import bpy
from bpy.props import CollectionProperty, IntProperty, StringProperty
from bpy.types import Panel, PropertyGroup, Scene, UIList


class LIST_ITEM_Entry(PropertyGroup):
    label: StringProperty()


class LIST_ITEM_UL_entries(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        assert_type(data, Scene)
        assert_type(item, LIST_ITEM_Entry)  # ty: ignore[blender-assumed-list-item]
        layout.label(text=item.label)  # ty: ignore[blender-assumed-list-item]


class LIST_ITEM_PT_entries(Panel):
    bl_label = "Entries"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        self.layout.template_list(
            "LIST_ITEM_UL_entries", "", context.scene, "list_item_entries", context.scene, "list_item_index"
        )


classes = (LIST_ITEM_Entry, LIST_ITEM_UL_entries, LIST_ITEM_PT_entries)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    Scene.list_item_entries = CollectionProperty(type=LIST_ITEM_Entry)
    Scene.list_item_index = IntProperty()


def unregister():
    del Scene.list_item_index
    del Scene.list_item_entries
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
