"""Feature test: what an addon registers is visible in that addon only. regchk_isolation_a and _b both import
regchk_shared_lib; only regchk_isolation_a calls its register_tool()."""

import bpy
import regchk_shared_lib
from bpy.props import IntProperty
from bpy.types import Operator


class REGCHK_ISOLATION_B_OT_run(Operator):
    bl_idname = "regchk_isolation_b.run"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(REGCHK_ISOLATION_B_OT_run)
    bpy.types.Scene.regchk_isolation_b_value = IntProperty()


def unregister():
    del bpy.types.Scene.regchk_isolation_b_value
    bpy.utils.unregister_class(REGCHK_ISOLATION_B_OT_run)
