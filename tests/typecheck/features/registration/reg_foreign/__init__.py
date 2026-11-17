"""Feature test: register() registers the values of a dict, which the checker cannot follow to their classes. It
gives up instead of dropping them, so every Blender class of the add-on counts as registered."""

import bpy
from bpy.types import Operator


class REG_FOREIGN_OT_first(Operator):
    bl_idname = "reg_foreign.first"
    bl_label = "First"

    def execute(self, context):
        return {"FINISHED"}


class REG_FOREIGN_OT_second(Operator):
    bl_idname = "reg_foreign.second"
    bl_label = "Second"

    def execute(self, context):
        return {"FINISHED"}


CLASSES = {"first": REG_FOREIGN_OT_first, "second": REG_FOREIGN_OT_second}


def register():
    for cls in CLASSES.values():
        bpy.utils.register_class(cls)  # ty: ignore[blender-assumed-complete-registration]


def unregister():
    for cls in reversed(list(CLASSES.values())):
        bpy.utils.unregister_class(cls)
