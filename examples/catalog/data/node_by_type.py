# /// catalog
# title = "`nodes.new(\"ShaderNodeBsdfPrincipled\")`"
# section = "nodes"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["type_narrowing"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs do not give each node class its idname, which the checker reads, so `nodes.new` stays a plain `Node`."
# "fake-bpy-module/5.2" = "These stubs do not give each node class its idname, which the checker reads, so `nodes.new` stays a plain `Node`."
# ///
"""`nodes.new` takes the idname of the node to create, as a string. The stubs return a plain `Node`; the checker types
the result as the node the idname names, so its own properties and sockets are known."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import ShaderNodeBsdfPrincipled, ShaderNodeTree


def example(tree: ShaderNodeTree) -> None:
    principled = tree.nodes.new("ShaderNodeBsdfPrincipled")
    assert_type(principled, ShaderNodeBsdfPrincipled)
    principled.distribution = "GGX"
