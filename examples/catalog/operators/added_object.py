# /// catalog
# title = "The object an `*_add` operator adds"
# section = "calls"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["assumptions"]
# see = ["blender/source/blender/editors/object/object_add.cc"]
#
# [evidence]
# addon = "assumptions/asm_added_object"
# rule = "blender-assumed-added-object"
# lenient = "warn"
# default = "warn"
# strict = "error"
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs type `context.object` as `Object`, so nothing is assumed, and with no Tag views `cube.data` stays the base type."
# "fake-bpy-module/5.2" = "These stubs have no Tag views, so `cube.data` stays the base type."
# ///
"""`bpy.ops.mesh.primitive_cube_add()` and the other `*_add` operators add an object and make it the active one, so
code reads it as `context.object` right after the call. Whether the call added an object does not show in the code.
The checker takes the read as the added object, a mesh object for
`primitive_cube_add`, and reports it as an Assumption."""

# catalog: hide
from typing import assert_type

# catalog: show
import bpy
from bpy.types import Context, Mesh


def add_cube(context: Context) -> None:
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    cube = context.object  # ty: ignore[blender-assumed-added-object]
    assert_type(cube.data, Mesh)
    cube.name = "Cube"
