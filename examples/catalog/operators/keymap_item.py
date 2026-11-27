# /// catalog
# title = "A key map item's properties"
# section = "idnames"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["operator_properties"]
# ///
"""`keymap_items.new("category.name", ...)` binds a key to an operator; its `properties` are the values the key passes.
The checker maps the idname to the operator, so `properties` has that operator's properties with their Value types,
not the stubs' generic `OperatorProperties`."""

# catalog: hide
from typing import assert_type

# catalog: show
import bpy
from bpy.props import IntProperty
from bpy.types import KeyMap, Operator


class Nudge(Operator):
    bl_idname = "operators.nudge"
    bl_label = "Nudge"

    steps: IntProperty(default=1)

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(Nudge)


def bind(keymap: KeyMap) -> None:
    item = keymap.keymap_items.new("operators.nudge", "RIGHT_ARROW", "PRESS", ctrl=True)
    assert_type(item.properties.steps, int)
    item.properties.steps = "5"  # ty: ignore[invalid-assignment]
