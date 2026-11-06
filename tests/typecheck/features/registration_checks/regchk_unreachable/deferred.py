"""Registers its operator from a timer that register() starts: Blender calls the function after register() returns,
so its registration is reachable."""

import bpy
from bpy.types import Operator


class REGCHK_UNREACHABLE_OT_late(Operator):
    bl_idname = "regchk_unreachable.late"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def late_register():
    bpy.utils.register_class(REGCHK_UNREACHABLE_OT_late)
    return None


def register():
    bpy.app.timers.register(late_register, first_interval=0.0)


def unregister():
    if bpy.app.timers.is_registered(late_register):
        bpy.app.timers.unregister(late_register)
    else:
        bpy.utils.unregister_class(REGCHK_UNREACHABLE_OT_late)
