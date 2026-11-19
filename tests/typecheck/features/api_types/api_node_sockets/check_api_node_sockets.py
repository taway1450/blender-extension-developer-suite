"""The stubs give each built-in node's `inputs` and `outputs` a class whose keys name sockets of known classes, by
identifier or name and by index; any other key gives a NodeSocket. These are stub facts."""

from __future__ import annotations

from typing import assert_type

from bpy.types import (CompositorNodeMovieDistortion, GeometryNodeMeshGrid, GeometryNodeRepeatInput,
                       GeometryNodeRepeatOutput, GeometryNodeStoreNamedAttribute, Node, NodeSocket, NodeSocketBool,
                       NodeSocketColor, NodeSocketFloat, NodeSocketFloatDistance, NodeSocketFloatFactor,
                       NodeSocketInt, NodeSocketMatrix, NodeSocketMenu, NodeSocketRotation, NodeSocketShader,
                       NodeSocketVector, NodeSocketVectorFactor, ShaderNodeBackground, ShaderNodeBsdfPrincipled,
                       ShaderNodeGroup, ShaderNodeMath, ShaderNodeMix)

# The socket of Store Named Attribute's value, one per data type.
StoreValue = (NodeSocketFloat | NodeSocketInt | NodeSocketBool | NodeSocketVector | NodeSocketColor | NodeSocketRotation
              | NodeSocketMatrix)


def principled(node: ShaderNodeBsdfPrincipled, key: str) -> None:
    assert_type(node.inputs["Base Color"], NodeSocketColor)  # bare-ok: a stub fact
    assert_type(node.inputs["Roughness"], NodeSocketFloatFactor)  # bare-ok: a stub fact
    assert_type(node.inputs["Normal"], NodeSocketVector)  # bare-ok: a stub fact
    assert_type(node.outputs["BSDF"], NodeSocketShader)  # bare-ok: a stub fact
    assert_type(node.inputs["Base Colour"], NodeSocket)  # bare-ok: a key the node does not declare
    assert_type(node.inputs[key], NodeSocket)  # bare-ok: a key that is not a literal
    assert_type(node.inputs[0:2], list[NodeSocket])  # bare-ok: a slice


def by_identifier_and_index(math: ShaderNodeMath, background: ShaderNodeBackground) -> None:
    assert_type(math.inputs["Value_001"], NodeSocketFloat)  # bare-ok: the identifier of the second input
    assert_type(background.inputs[0], NodeSocketColor)  # bare-ok: an index counts every socket
    assert_type(background.inputs[1], NodeSocketFloat)  # bare-ok: a stub fact
    assert_type(background.inputs[99], NodeSocket)  # bare-ok: an index past the declared sockets


def variants(mix: ShaderNodeMix, store: GeometryNodeStoreNamedAttribute) -> None:
    # The socket of a key changes with the node's data type: the key gives any of them.
    assert_type(mix.inputs["A"], NodeSocketFloat | NodeSocketVector | NodeSocketColor)  # bare-ok: a stub fact
    assert_type(mix.inputs["Factor"], NodeSocketFloatFactor | NodeSocketVectorFactor)  # bare-ok: a stub fact
    assert_type(mix.inputs["A_Float"], NodeSocket)  # bare-ok: Mix finds its sockets by name only
    assert_type(store.inputs["Value"], StoreValue)  # bare-ok: a stub fact


def other_trees(grid: GeometryNodeMeshGrid, distortion: CompositorNodeMovieDistortion) -> None:
    assert_type(grid.inputs["Size X"], NodeSocketFloatDistance)  # bare-ok: a geometry node
    assert_type(grid.inputs["Vertices X"], NodeSocketInt)  # bare-ok: a stub fact
    assert_type(distortion.inputs["Type"], NodeSocketMenu)  # bare-ok: a compositor node


def user_defined(group: ShaderNodeGroup, repeat_in: GeometryNodeRepeatInput, repeat_out: GeometryNodeRepeatOutput,
                 node: Node) -> None:
    assert_type(group.inputs["Color"], NodeSocket)  # bare-ok: a group's sockets come from its tree
    assert_type(repeat_in.inputs["Iterations"], NodeSocketInt)  # bare-ok: a socket the zone declares
    assert_type(repeat_out.inputs["Geometry"], NodeSocket)  # bare-ok: a repeat item's, which the user names
    assert_type(node.inputs["Color"], NodeSocket)  # bare-ok: any node
