# /// catalog
# title = "A class that is never registered"
# section = "classes"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["registration_checks"]
# ///
"""A Blender class does nothing until `register()` registers it: an operator missing from the list is not in
`bpy.ops`, a panel never shows. The checker reports a class the add-on defines but never registers. A class that only
serves as a base or a mixin for registered classes is not reported."""

import bpy
from bpy.types import Operator

bl_info = {
    "name": "Catalog: a class that is never registered",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


class NEVER_REGISTERED_OT_base(Operator):
    bl_label = "Base"

    def execute(self, context):
        return {"FINISHED"}


class NEVER_REGISTERED_OT_used(NEVER_REGISTERED_OT_base):
    bl_idname = "never_registered.used"
    bl_label = "Used"


class NEVER_REGISTERED_OT_forgotten(NEVER_REGISTERED_OT_base):  # ty: ignore[blender-unregistered-class]
    bl_idname = "never_registered.forgotten"
    bl_label = "Forgotten"


def register():
    bpy.utils.register_class(NEVER_REGISTERED_OT_used)


def unregister():
    bpy.utils.unregister_class(NEVER_REGISTERED_OT_used)


def example() -> None:
    bpy.ops.never_registered.used()
    bpy.ops.never_registered.forgotten()  # ty: ignore[missing-attribute]
