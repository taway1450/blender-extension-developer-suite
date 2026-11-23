"""Hover shows the object an `*_add` operator is taken to have made active (here in a test, which is not reported)."""

import bpy


def helper(context: bpy.types.Context):
    bpy.ops.mesh.primitive_cube_add()
    if context.object:
        #      ^hover
        pass
