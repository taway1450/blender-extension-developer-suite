"""Poll helpers the operator's poll() calls with its context: the checker follows them up to three calls deep."""


def in_node_editor(context):
    # Reading through context.space_data.edit_tree: a poll that raises is a failed poll.
    return _is_node_editor(context) and len(context.space_data.edit_tree.nodes) > 0


def _is_node_editor(context):
    space = context.space_data
    if space is None:
        return False
    return space.type == "NODE_EDITOR"
