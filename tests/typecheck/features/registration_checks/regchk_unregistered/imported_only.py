"""Imported and called by __init__.py, but its class is never registered."""

from bpy.types import Operator


class REGCHK_UNREGISTERED_OT_imported(Operator):  # ty: ignore[blender-unregistered-class]
    bl_idname = "regchk_unregistered.imported"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def helper():
    pass
