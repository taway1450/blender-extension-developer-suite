# /// catalog
# title = "Calling Blender's operators"
# section = "calls"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["operator_calls"]
# ///
"""Blender's own operators take their properties as keyword arguments, typed from the stubs: an enum property takes
one of its identifiers, and any other string is reported."""

import bpy


def example() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.select_all(action="ALL")  # ty: ignore[invalid-argument-type]
