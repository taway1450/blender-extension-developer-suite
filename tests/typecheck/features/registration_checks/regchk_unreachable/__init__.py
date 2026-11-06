"""Feature test: blender-unreachable-registration, on functions that register classes but that register() never
calls, directly or through other functions. What they register is not in bpy.ops. A function register() hands to a
timer is reachable (deferred.py)."""

import bpy
from bpy.types import Operator

from . import deferred, forgotten, used


class REGCHK_UNREACHABLE_OT_extra(Operator):
    bl_idname = "regchk_unreachable.extra"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def _register_extra():  # ty: ignore[blender-unreachable-registration]
    bpy.utils.register_class(REGCHK_UNREACHABLE_OT_extra)


def register():
    used.register()
    deferred.register()


def unregister():
    deferred.unregister()
    used.unregister()
