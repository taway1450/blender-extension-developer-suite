"""A Type tag test of an add-on's own node: its bl_idname names the add-on's registered class."""

from __future__ import annotations

from typing import assert_type

from bpy.types import Node, ShaderNodeMath

from . import NarrowValuesNode, NarrowValuesOtherNode


def own_node(node: Node) -> None:
    if node.bl_idname == 'NarrowValuesNode':
        assert_type(node, NarrowValuesNode)  # oracle-skip: a narrowing, which a stub cannot state
    if node.bl_idname in ('NarrowValuesNode', 'NarrowValuesOtherNode', 'ShaderNodeMath'):
        assert_type(node, NarrowValuesNode | NarrowValuesOtherNode | ShaderNodeMath)  # oracle-skip: a narrowing
    if node.bl_idname == 'NarrowValuesMissingNode':
        assert_type(node, Node)  # bare-ok: no class has this bl_idname
    if node.bl_idname != 'NarrowValuesNode':
        assert_type(node, Node)  # bare-ok: a subclass of the add-on's node has a bl_idname of its own
