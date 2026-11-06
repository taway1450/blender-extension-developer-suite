"""What a Type tag test does not narrow: an add-on's own node, whose bl_idname no stub class declares."""

from __future__ import annotations

from typing import assert_type

from bpy.types import Node


def own_node(node: Node) -> None:
    if node.bl_idname == 'NarrowValuesNode':
        assert_type(node, Node)  # bare-ok: an add-on's own node class is not in the Type tag table
