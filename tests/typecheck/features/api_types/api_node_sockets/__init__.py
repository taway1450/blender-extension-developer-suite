"""Feature test: a built-in node declares its sockets, so a key of its `inputs` or `outputs` names a socket of a
known class. `principled.inputs["Base Color"]` is a NodeSocketColor: Blender finds an available socket whose
identifier is the key, else one whose name is (Mix and Map Range only by name), and an index counts every socket.
A key a node gives different sockets for in different states is the union (`mix.inputs["A"]`). The stubs must state
it (check_api_node_sockets.py); below, the node comes from `nodes.new`, which the checker narrows, and the helpers
build the nodes for the runtime probes (_expected/runtime.toml)."""

from typing import assert_type

import bpy
from bpy.types import NodeSocketColor, NodeSocketFloat, NodeSocketFloatFactor, NodeSocketShader, NodeTree


def principled_material(tree: NodeTree) -> None:
    principled = tree.nodes.new('ShaderNodeBsdfPrincipled')
    assert_type(principled.inputs["Base Color"], NodeSocketColor)
    principled.inputs["Base Color"].default_value = (0.8, 0.1, 0.1, 1.0)
    principled.inputs["Roughness"].default_value = 0.4
    assert_type(principled.outputs["BSDF"], NodeSocketShader)
    output = tree.nodes.new(type='ShaderNodeOutputMaterial')
    tree.links.new(principled.outputs["BSDF"], output.inputs["Surface"])


def math_node(tree: NodeTree) -> None:
    node = tree.nodes.new('ShaderNodeMath')
    assert_type(node.inputs[1], NodeSocketFloat)
    assert_type(node.inputs["Value_001"], NodeSocketFloat)
    node.inputs[1].default_value = 2.0


def mix_factor(tree: NodeTree) -> None:
    mix = tree.nodes.new('ShaderNodeMix')
    factor = mix.inputs["Factor"]
    if isinstance(factor, NodeSocketFloatFactor):
        factor.default_value = 0.5


_NAME = "api_node_sockets"


def socket_class(tree_type, node_type, side, key, **props):
    """The class name of the socket ``key`` finds on a new ``node_type`` node with ``props`` set, or the error."""
    tree = bpy.data.node_groups.new(_NAME, tree_type)
    try:
        node = tree.nodes.new(node_type)
        for name, value in props.items():
            setattr(node, name, value)
        try:
            return type(getattr(node, side)[key]).__name__
        except (KeyError, IndexError) as ex:
            return type(ex).__name__
    finally:
        bpy.data.node_groups.remove(tree)


def register():
    pass


def unregister():
    pass
