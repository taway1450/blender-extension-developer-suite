# /// catalog
# title = "A socket's `default_value`"
# section = "nodes"
# status = "partial"
# safeguards = ["typechecker"]
# features = ["assumptions"]
# later = "subclass-member-writes"
# note = "A read of `default_value` on a plain `NodeSocket` is assumed; a write is still an error."
#
# [future]
# class = "planned"
# note = "Accept a write to a member only a subclass has, as the read is."
# tracked = "later/subclass-member-writes"
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs report the read of `default_value` on `NodeSocket` as missing instead of assuming it."
# "fake-bpy-module/5.2" = "These stubs reject a key that is not a literal name of the node's sockets, so the socket is unknown and neither the read nor the write is reported."
# ///
"""Every socket type that holds a value has a `default_value`, but the base `NodeSocket` does not. A socket found by a
name that is not a literal is a plain `NodeSocket`; the checker takes it to be one of the socket types with a
`default_value`, accepts the read and reports it as an Assumption. A write there is not accepted yet."""

from bpy.types import ShaderNodeBsdfPrincipled


def example(principled: ShaderNodeBsdfPrincipled, name: str) -> None:
    socket = principled.inputs[name]
    print(socket.default_value)  # ty: ignore[blender-assumed-subclass-member]
    # gap: a write to a subclass member is an error
    socket.default_value = 0.5
