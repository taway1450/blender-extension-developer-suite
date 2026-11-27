# /// catalog
# title = "`layout.operator` and its properties"
# section = "draw"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["operator_properties"]
# ///
"""`layout.operator` draws a button for an operator and returns the properties the button will run it with. The
checker finds the operator by its idname, Blender's or the add-on's own, and types the returned properties as that
operator's, so each property has its own type and a wrong value is reported."""

# catalog: hide
from typing import Literal, assert_type

# catalog: show
from bpy.types import Panel


class SelectPanel(Panel):
    bl_label = "Select"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        props = self.layout.operator("object.select_all")
        assert_type(props.action, Literal["TOGGLE", "SELECT", "DESELECT", "INVERT"])
        props.action = "ALL"  # ty: ignore[invalid-assignment]
