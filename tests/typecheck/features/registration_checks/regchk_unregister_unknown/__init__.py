"""Feature test: blender-unregister-mismatch, on unregister_class for a class register() never registers: Blender
raises RuntimeError (missing bl_rna attribute)."""

import bpy
from bpy.types import Operator


class REGCHK_UNREGISTER_UNKNOWN_OT_registered(Operator):
    bl_idname = "regchk_unregister_unknown.registered"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_UNREGISTER_UNKNOWN_OT_never(Operator):  # ty: ignore[blender-unregistered-class]
    bl_idname = "regchk_unregister_unknown.never"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(REGCHK_UNREGISTER_UNKNOWN_OT_registered)


def unregister():
    bpy.utils.unregister_class(REGCHK_UNREGISTER_UNKNOWN_OT_never)  # ty: ignore[blender-unregister-mismatch]
    bpy.utils.unregister_class(REGCHK_UNREGISTER_UNKNOWN_OT_registered)
