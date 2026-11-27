# /// catalog
# title = "Pointers Blender keeps in step"
# section = "pointers"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["pointer_aliases", "implied_narrowings"]
# see = ["blender/source/blender/editors/space_node/space_node.cc"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs have no Tag views, so `context.space_data` stays `Space | None`, and `Space` has no `node_tree` or `edit_tree`: each read is reported."
# "fake-bpy-module/5.2" = "These stubs have no Tag views, so `context.space_data` stays `Space | None`, and `Space` has no `node_tree` or `edit_tree`: each read is reported."
# ///
"""Blender's C code keeps some pointers in step: in the node editor, `space_data.node_tree` being set means
`space_data.edit_tree` is set too, since Blender sets and clears the two together. The checker applies such a
Pointer alias without reporting it: a poll that checks `node_tree` also covers `edit_tree`. The read of `node_tree`
itself is reported as the narrowing the poll implies; the read of `edit_tree`, which the alias adds, is not."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import NodeTree, Panel


class SIMPLE_PT_node_tree(Panel):
    bl_label = "Node tree"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"

    @classmethod
    def poll(cls, context):
        return context.space_data.node_tree is not None

    def draw(self, context):
        assert_type(context.space_data.node_tree, NodeTree)  # ty: ignore[blender-narrowed-by-poll]
        assert_type(context.space_data.edit_tree, NodeTree)
