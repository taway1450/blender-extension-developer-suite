# /// catalog
# title = "A class registered twice"
# section = "classes"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["registration_checks"]
#
# [evidence]
# addon = "registration_checks/regchk_duplicate"
# register = "fails"
# says = "class registered twice"
# ///
"""Registering a class that is already registered raises `ValueError`, so the add-on fails to enable. It happens
when a class is both registered by hand and listed in the tuple a loop registers. The checker reports the class where
it is registered again: here, its place in the tuple."""

import bpy
from bpy.types import Operator

bl_info = {
    "name": "Catalog: a class registered twice",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


class REGISTERED_TWICE_OT_run(Operator):
    bl_idname = "registered_twice.run"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


classes = (REGISTERED_TWICE_OT_run,)  # ty: ignore[blender-duplicate-registration]


def register():
    bpy.utils.register_class(REGISTERED_TWICE_OT_run)
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
