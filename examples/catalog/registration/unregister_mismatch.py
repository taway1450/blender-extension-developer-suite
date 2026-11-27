# /// catalog
# title = "`unregister()` that does not undo `register()`"
# section = "classes"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["registration_checks"]
#
# [evidence]
# addon = "registration_checks/regchk_unregister_unknown"
# register = "fails"
# says = "unregister_class for a class that is not registered"
# ///
"""`unregister()` should remove what `register()` added: what it leaves behind stays in Blender after the add-on is
disabled, and `unregister_class` for a class that was never registered raises. The checker compares the two
functions and reports each difference; a class only `unregister()` names is also never registered."""

import bpy
from bpy.props import IntProperty
from bpy.types import Operator

bl_info = {
    "name": "Catalog: unregister() that does not undo register()",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


class UNREGISTER_MISMATCH_OT_run(Operator):
    bl_idname = "unregister_mismatch.run"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class UNREGISTER_MISMATCH_OT_other(Operator):  # ty: ignore[blender-unregistered-class]
    bl_idname = "unregister_mismatch.other"
    bl_label = "Other"

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(UNREGISTER_MISMATCH_OT_run)
    bpy.types.Scene.mismatch_count = IntProperty()  # ty: ignore[blender-unregister-mismatch]


def unregister():
    bpy.utils.unregister_class(UNREGISTER_MISMATCH_OT_run)
    bpy.utils.unregister_class(UNREGISTER_MISMATCH_OT_other)  # ty: ignore[blender-unregister-mismatch]
