"""The Add menu entry and the sidebar panel of the node editor."""

from __future__ import annotations

import bpy
from bpy.types import Menu, Panel

CALCULATOR_NODES = (("KitValueNode", "Value"), ("KitMathNode", "Math"))


class NODE_MT_kit_add(Menu):
    bl_label = "Kit"

    def draw(self, context):
        layout = self.layout
        # A menu names no editor, but its idname starts with the node editor's prefix.
        # demo: blender-narrowed-by-menu-prefix
        if context.space_data.tree_type == "KitNodeTree":
            for idname, label in CALCULATOR_NODES:
                # demo: operator_properties
                props = layout.operator("node.add_node", text=label)
                props.type = idname
                props.use_transform = True
        else:
            layout.operator("node.kit_principled_setup")
            layout.operator("node.kit_tint_active")


def draw_add_menu(self, context):
    self.layout.menu("NODE_MT_kit_add")


class NODE_PT_kit(Panel):
    bl_label = "Node Kit"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Kit"

    def draw(self, context):
        layout = self.layout
        # demo: context_members
        space = context.space_data
        if space.tree_type == "KitNodeTree":
            layout.operator("node.kit_new_tree", icon="ADD")
            layout.operator("node.kit_evaluate", icon="PLAY")
        elif space.tree_type == "ShaderNodeTree":
            layout.operator("node.kit_principled_setup")
            layout.operator("node.kit_append_assets", icon="APPEND_BLEND")
            # Node Wrangler's operator: the button is there only while that add-on is enabled.
            if hasattr(bpy.types, "NODE_OT_nw_add_textures_for_principled"):
                # demo: blender-unknown-operator
                layout.operator("node.nw_add_textures_for_principled")

        node = context.active_node
        if node is not None:
            layout.separator()
            layout.prop(node, "label")
            layout.prop(node, "use_custom_color")


classes = (NODE_MT_kit_add, NODE_PT_kit)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.NODE_MT_add.append(draw_add_menu)


def unregister():
    bpy.types.NODE_MT_add.remove(draw_add_menu)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
