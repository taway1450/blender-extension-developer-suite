# /// catalog
# title = "`bpy.data.materials[\"Rust\"]`"
# section = "by-name"
# status = "partial"
# safeguards = ["stub-generator"]
# features = ["api_types"]
# later = "blend-file-typing"
# note = "A material found by name is a `Material`, but the nodes it holds in the file are not known."
# blender-docs = ["info_quickstart"]
#
# [future]
# class = "planned"
# note = "Read the `.blend` files the add-on ships and type their data-blocks by name, with the nodes of their trees."
# tracked = "later/blend-file-typing"
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs type `material.node_tree` as `NodeTree | None`, so the read of `nodes` is reported too."
# "fake-bpy-module/5.2" = "These stubs type `material.node_tree` as `NodeTree | None`, so the read of `nodes` is reported too."
# ///
"""What a material found by name holds, such as the nodes of its tree, is not known: only the `.blend` file it comes
from says. `bpy.data.materials["Rust"]` is a `Material`, as any lookup by name gives its collection's type, and its
`node_tree` is set, but a node found by name there is a plain `Node`."""

# catalog: hide
from typing import assert_type

# catalog: show
import bpy
from bpy.types import Material, ShaderNodeBsdfPrincipled


def example() -> None:
    rust = bpy.data.materials["Rust"]
    assert_type(rust, Material)
    # gap: the nodes of a material in a file are not known
    assert_type(rust.node_tree.nodes["Principled BSDF"], ShaderNodeBsdfPrincipled)
