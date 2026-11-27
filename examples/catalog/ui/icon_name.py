# /// catalog
# title = "Icons by name"
# section = "draw"
# status = "handled"
# safeguards = ["stub-generator"]
# features = ["api_types"]
# ///
"""A layout function takes an icon by its name, such as `icon="ERROR"`. The stubs type `icon` as the set of Blender's
icon names, so a misspelt name is reported."""

from bpy.types import Panel


class WarningPanel(Panel):
    bl_label = "Warning"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        self.layout.label(text="Check the scale", icon="ERRORR")  # ty: ignore[invalid-argument-type]
