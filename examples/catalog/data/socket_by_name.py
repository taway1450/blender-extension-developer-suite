# /// catalog
# title = "Sockets by name"
# section = "nodes"
# status = "partial"
# safeguards = ["stub-generator", "runtime-probe"]
# features = ["api_types"]
# note = "A name the node does not declare gives a plain `NodeSocket`, not an error."
#
# [future]
# class = "possible"
# note = "Type the lookup by the node's socket names only, so another name is reported, as fake-bpy-module does for 5.2."
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs do not type a node's sockets by name, so each is a plain `NodeSocket` and the asserts fail."
# "fake-bpy-module/5.2" = "These stubs type a node's sockets by an overload of their names, so a name the node does not declare is reported."
# ///
"""A built-in node's sockets are looked up by name, identifier or index, and each has its own socket type: the Principled
BSDF's `"Base Color"` input is a `NodeSocketColor`. Blender's API docs build probes each node for its sockets, and the
stubs carry what it finds. A name the node does not declare gives a plain `NodeSocket` and is not reported; the marked
line shows the result a check would give."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import NodeSocketColor, NodeSocketShader, ShaderNodeBsdfPrincipled


def example(principled: ShaderNodeBsdfPrincipled) -> None:
    assert_type(principled.inputs["Base Color"], NodeSocketColor)
    assert_type(principled.outputs["BSDF"], NodeSocketShader)
    # gap: a name the node does not declare is not reported
    print(principled.inputs["Base Colour"])  # ty: ignore[invalid-argument-type]
