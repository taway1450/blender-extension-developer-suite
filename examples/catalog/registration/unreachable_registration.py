# /// catalog
# title = "Registration outside `register()`"
# section = "reach"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["registration_checks"]
# ///
"""Only what `register()` reaches is registered when the add-on is enabled. A function that registers a class but
that `register()` never calls, directly or through other functions (a timer it starts counts), is reported, and its
operator is not in `bpy.ops`."""

import bpy
from bpy.types import Operator

bl_info = {
    "name": "Catalog: registration outside register()",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


class UNREACHABLE_REGISTRATION_OT_run(Operator):
    bl_idname = "unreachable_registration.run"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class UNREACHABLE_REGISTRATION_OT_extra(Operator):
    bl_idname = "unreachable_registration.extra"
    bl_label = "Extra"

    def execute(self, context):
        return {"FINISHED"}


def register_extra():  # ty: ignore[blender-unreachable-registration]
    bpy.utils.register_class(UNREACHABLE_REGISTRATION_OT_extra)


def register():
    bpy.utils.register_class(UNREACHABLE_REGISTRATION_OT_run)


def unregister():
    bpy.utils.unregister_class(UNREACHABLE_REGISTRATION_OT_run)


def example() -> None:
    bpy.ops.unreachable_registration.run()
    bpy.ops.unreachable_registration.extra()  # ty: ignore[missing-attribute]
