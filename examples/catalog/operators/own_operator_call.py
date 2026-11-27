# /// catalog
# title = "Calling the add-on's own operator"
# section = "calls"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["operator_calls"]
# ///
"""Once registered, an operator is called as `bpy.ops.<category>.<name>(...)`, one keyword argument per property. The
checker reads the registered class, so each keyword is typed as its property: an `IntProperty` takes an `int`, an
`EnumProperty` with static items one of its identifiers."""

import bpy
from bpy.props import EnumProperty, IntProperty
from bpy.types import Operator


class Scatter(Operator):
    bl_idname = "operators.scatter"
    bl_label = "Scatter"

    count: IntProperty(default=10)
    mode: EnumProperty(items=[("GRID", "Grid", ""), ("RANDOM", "Random", "")])

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(Scatter)


def example() -> None:
    bpy.ops.operators.scatter(count=20, mode="GRID")
    bpy.ops.operators.scatter(count=20, mode="CIRCLE")  # ty: ignore[invalid-argument-type]
