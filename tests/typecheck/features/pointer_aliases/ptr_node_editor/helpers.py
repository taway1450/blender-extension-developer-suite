"""Poll helpers in the style of Node Wrangler's nw_check / nw_check_active."""


def node_editor_check(cls, context):
    space = context.space_data
    if space.type != "NODE_EDITOR":
        cls.poll_message_set("Current editor is not a node editor.")
        return False
    if space.node_tree is None:
        cls.poll_message_set("No node tree was found in the current node editor.")
        return False
    return True


def active_check(cls, context):
    if context.active_node is None or not context.active_node.select:
        cls.poll_message_set("No active node.")
        return False
    return True
