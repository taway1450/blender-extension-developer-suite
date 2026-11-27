# /// catalog
# title = "Registration in a helper function"
# section = "reach"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["registration"]
# ///
"""`register()` often hands the work to helper functions. The checker follows every call `register()` makes, also into
the `register()` of a submodule, so an operator a helper registers is in `bpy.ops` with its properties."""

import bpy
from bpy.props import IntProperty
from bpy.types import Operator

bl_info = {
    "name": "Catalog: registration in a helper function",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


class HELPER_REGISTRATION_OT_run(Operator):
    bl_idname = "helper_registration.run"
    bl_label = "Run"

    count: IntProperty()

    def execute(self, context):
        return {"FINISHED"}


def register_operators():
    bpy.utils.register_class(HELPER_REGISTRATION_OT_run)


def register():
    register_operators()


def unregister():
    bpy.utils.unregister_class(HELPER_REGISTRATION_OT_run)


def example() -> None:
    bpy.ops.helper_registration.run(count=2)
    bpy.ops.helper_registration.run(count="2")  # ty: ignore[invalid-argument-type]
