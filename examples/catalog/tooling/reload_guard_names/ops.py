import bpy
from bpy.types import Operator


class RELOAD_GUARD_NAMES_OT_run(Operator):
    bl_idname = "reload_guard_names.run"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(RELOAD_GUARD_NAMES_OT_run)


def unregister():
    bpy.utils.unregister_class(RELOAD_GUARD_NAMES_OT_run)
