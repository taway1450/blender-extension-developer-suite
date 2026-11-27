# /// catalog
# title = "Registration under a condition"
# section = "reach"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["registration", "assumptions"]
# ///
"""A class that `register()` registers only under a condition (a Blender version check, an environment variable)
exists only when the condition held. The checker counts it as registered, so its operator is in `bpy.ops`, and reports
each use as an Assumption."""

import bpy
from bpy.types import Operator

bl_info = {
    "name": "Catalog: registration under a condition",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


class CONDITIONAL_REGISTRATION_OT_new(Operator):
    bl_idname = "conditional_registration.new"
    bl_label = "New"

    def execute(self, context):
        return {"FINISHED"}


def register():
    if bpy.app.version >= (4, 3, 0):
        bpy.utils.register_class(CONDITIONAL_REGISTRATION_OT_new)


def unregister():
    if bpy.app.version >= (4, 3, 0):
        bpy.utils.unregister_class(CONDITIONAL_REGISTRATION_OT_new)


def example() -> None:
    bpy.ops.conditional_registration.new()  # ty: ignore[blender-assumed-registration]
