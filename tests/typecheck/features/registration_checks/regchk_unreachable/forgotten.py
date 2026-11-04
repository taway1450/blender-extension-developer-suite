"""Imported by __init__.py, but its register() is never called."""

import bpy
from bpy.types import Operator


class REGCHK_UNREACHABLE_OT_lost(Operator):
    bl_idname = "regchk_unreachable.lost"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def register():  # ty: ignore[blender-unreachable-registration]
    bpy.utils.register_class(REGCHK_UNREACHABLE_OT_lost)


def unregister():
    bpy.utils.unregister_class(REGCHK_UNREACHABLE_OT_lost)
