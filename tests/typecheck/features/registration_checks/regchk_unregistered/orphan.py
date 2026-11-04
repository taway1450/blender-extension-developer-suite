"""Never imported: its classes belong to the addon (they are in its folder) and are never registered."""

from bpy.types import Operator


class REGCHK_UNREGISTERED_OT_orphan(Operator):  # ty: ignore[blender-unregistered-class]
    bl_idname = "regchk_unregistered.orphan"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}
