"""Hover shows the type a Pointer alias narrows a read to."""

from . import PTR_NODE_OT_active, PTR_NODE_PT_node_tree


class _EditTree(PTR_NODE_PT_node_tree):
    def draw(self, context):
        context.space_data.edit_tree
        #                  ^hover-contains "NodeTree"


class _Active(PTR_NODE_OT_active):
    def execute(self, context):
        context.space_data.edit_tree.nodes.active
        #                                  ^hover
        return {"FINISHED"}
