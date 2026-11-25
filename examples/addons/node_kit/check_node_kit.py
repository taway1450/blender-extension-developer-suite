"""The types the add-on's code relies on. Blender never imports this file (see ../README.md)."""

from __future__ import annotations

from typing import Literal, assert_type

import bpy
from bpy.types import (
    GeometryNodeTree,
    Node,
    NodeSocketColor,
    NodeTree,
    ShaderNodeBsdfPrincipled,
    ShaderNodeTexImage,
    ShaderNodeTree,
)

from .tree import KitFloatSocket, KitMathNode, KitNodeTree


def built_in_nodes(tree: ShaderNodeTree) -> None:
    # A node made by its idname is that node.
    # demo: type_narrowing
    shader = tree.nodes.new("ShaderNodeBsdfPrincipled")
    assert_type(shader, ShaderNodeBsdfPrincipled)
    # The sockets of a built-in node, by name.
    # demo: api_types
    assert_type(shader.inputs["Base Color"], NodeSocketColor)
    assert_type(shader.inputs["Roughness"].default_value, float)


def type_tags(node: Node) -> None:
    if node.type == "TEX_IMAGE":
        assert_type(node, ShaderNodeTexImage)


def own_properties(node: KitMathNode, socket: KitFloatSocket) -> None:
    # Properties of the add-on's own nodes and sockets.
    # demo: properties
    assert_type(node.operation, Literal["ADD", "MULTIPLY", "MAXIMUM"])
    assert_type(socket.value, float)


def own_types(tree: NodeTree, node: KitMathNode) -> None:
    # A node made by the idname of one of the add-on's node classes is that class.
    # demo: type_narrowing
    assert_type(tree.nodes.new("KitMathNode"), KitMathNode)
    # A tree made by the idname of the add-on's tree class is not: the stubs only take the built-in names.
    # demo: later/own-node-tree-types
    assert_type(bpy.data.node_groups.new("Calculator", "KitNodeTree"), KitNodeTree)
    # The sockets a node's `init` makes, by name.
    # demo: later/own-node-sockets
    assert_type(node.inputs["A"], KitFloatSocket)


def shipped_file() -> None:
    # The data-blocks of assets.blend, by name.
    # demo: later/blend-file-typing
    assert_type(bpy.data.node_groups["Scatter Points"], GeometryNodeTree)
    rust_nodes = bpy.data.materials["Rust"].node_tree.nodes
    # demo: later/blend-file-typing
    assert_type(rust_nodes["Principled BSDF"], ShaderNodeBsdfPrincipled)
