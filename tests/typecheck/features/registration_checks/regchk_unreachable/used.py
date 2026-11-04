"""Its register() is called by the addon's register()."""

import bpy
from bpy.types import Operator


class REGCHK_UNREACHABLE_OT_used(Operator):
    bl_idname = "regchk_unreachable.used"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(REGCHK_UNREACHABLE_OT_used)


def unregister():
    bpy.utils.unregister_class(REGCHK_UNREACHABLE_OT_used)
