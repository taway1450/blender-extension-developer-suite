import bpy
from bpy.types import Operator

LABEL = "Run"


class RELOAD_GUARD_OT_run(Operator):
    bl_idname = "reload_guard.run"
    bl_label = LABEL

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(RELOAD_GUARD_OT_run)


def unregister():
    bpy.utils.unregister_class(RELOAD_GUARD_OT_run)
