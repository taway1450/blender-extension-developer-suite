"""Feature test: pointers of the node editor that Blender keeps in step (Pointer aliases).

- space_data.node_tree being set means space_data.edit_tree is set: ED_node_tree_start sets both to the same tree,
  ED_node_tree_push / ED_node_tree_pop keep edit_tree the last entry of the tree path, whose root is never popped, and
  node_id_remap clears both together (space_node.cc).
- context.active_node is space_data.edit_tree.nodes.active: only the node editor provides it, as
  node_get_active(*snode->edittree) (space_node.cc).

A check on one pointer is a check on the other. The poll that checked it is still reported where its own path is read
(context.space_data), but what the alias adds is not.

The assert_type calls in the bodies are no-ops at runtime."""

from typing import assert_type

import bpy
from bpy.types import Node, NodeTree, Operator, Panel

from .helpers import active_check, node_editor_check


class PTR_NODE_OT_edit_tree(Operator):
    """Like Node Wrangler's operators: nw_check checks node_tree, execute reads edit_tree."""

    bl_idname = "ptr_node.edit_tree"
    bl_label = "Edit tree"

    @classmethod
    def poll(cls, context):
        return node_editor_check(cls, context)

    def execute(self, context):
        tree = context.space_data.edit_tree  # ty: ignore[blender-narrowed-by-poll]
        assert_type(tree, NodeTree)  # oracle-skip: a Pointer alias, silent
        nodes = tree.nodes
        nodes.active.name  # ty: ignore[missing-union-attribute]  # bare-ok: no poll checked the active node
        return {"FINISHED"}


class PTR_NODE_OT_active(Operator):
    """nw_check_active checks context.active_node, execute reads edit_tree.nodes.active."""

    bl_idname = "ptr_node.active"
    bl_label = "Active node"

    @classmethod
    def poll(cls, context):
        return node_editor_check(cls, context) and active_check(cls, context)

    def execute(self, context):
        tree = context.space_data.edit_tree  # ty: ignore[blender-narrowed-by-poll]
        nodes = tree.nodes
        active = nodes.active
        assert_type(active, Node)  # oracle-skip: a Pointer alias, silent
        assert_type(context.space_data.edit_tree.nodes.active, Node)  # ty: ignore[blender-narrowed-by-poll]
        return {"FINISHED"}


class PTR_NODE_PT_edit_tree_active(Panel):
    """The other direction: the poll checks edit_tree.nodes.active, draw reads context.active_node."""

    bl_label = "Active node"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Aliases"

    @classmethod
    def poll(cls, context):
        tree = context.space_data.edit_tree
        return tree is not None and tree.nodes.active is not None

    def draw(self, context):
        assert_type(context.active_node, Node)  # oracle-skip: a Pointer alias, silent
        context.space_data.node_tree.name  # ty: ignore[missing-union-attribute]  # bare-ok: edit_tree does not imply node_tree


class PTR_NODE_PT_node_tree(Panel):
    bl_label = "Node tree"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Aliases"

    @classmethod
    def poll(cls, context):
        return context.space_data.node_tree is not None

    def draw(self, context):
        assert_type(context.space_data.node_tree, NodeTree)  # ty: ignore[blender-narrowed-by-poll]
        assert_type(context.space_data.edit_tree, NodeTree)  # oracle-skip: a Pointer alias, silent
        context.active_node.name  # ty: ignore[missing-union-attribute]  # bare-ok: node_tree does not imply an active node


classes = (PTR_NODE_OT_edit_tree, PTR_NODE_OT_active, PTR_NODE_PT_edit_tree_active, PTR_NODE_PT_node_tree)
register, unregister = bpy.utils.register_classes_factory(classes)
