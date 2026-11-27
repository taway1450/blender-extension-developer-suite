# /// catalog
# title = "A class variable Blender reads"
# section = "overrides"
# status = "handled"
# safeguards = ["stub-generator"]
# features = ["inheritance"]
# ///
"""The stubs declare the class variables Blender reads at registration, such as `bl_options` and `bl_space_type`,
with their allowed values, so a misspelt value is reported like any other wrong value."""

from bpy.types import Operator, Panel


class Apply(Operator):
    bl_idname = "inheritance.apply"
    bl_label = "Apply"
    bl_options = {"REGISTER", "UNDOO"}  # ty: ignore[invalid-assignment]


class Tools(Panel):
    bl_label = "Tools"
    bl_space_type = "VIEW3D"  # ty: ignore[invalid-assignment]
    bl_region_type = "UI"

    def draw(self, context):
        pass
