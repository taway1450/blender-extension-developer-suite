# /// catalog
# title = "Classes `register()` finds at runtime"
# section = "reach"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["registration", "assumptions"]
# ///
"""When `register()` registers classes it finds while it runs (`getattr` on a module, an `auto_load` helper), the
checker counts every Blender class of the add-on as registered and says so once, as an Assumption. It cannot tell
which classes they are, so it turns off its checks for classes missing from `register()`."""

import sys

import bpy
from bpy.types import Operator

bl_info = {
    "name": "Catalog: classes register() finds at runtime",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}

CLASS_NAMES = ("REGISTRATION_AT_RUNTIME_OT_run",)


class REGISTRATION_AT_RUNTIME_OT_run(Operator):
    bl_idname = "registration_at_runtime.run"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def register():
    module = sys.modules[__name__]
    for name in CLASS_NAMES:
        bpy.utils.register_class(getattr(module, name))  # ty: ignore[blender-assumed-complete-registration]


def unregister():
    module = sys.modules[__name__]
    for name in reversed(CLASS_NAMES):
        bpy.utils.unregister_class(getattr(module, name))


def example() -> None:
    bpy.ops.registration_at_runtime.run()
