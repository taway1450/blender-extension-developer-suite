from bpy.types import Operator


class REGCHK_MAIN_GUARD_OT_run(Operator):
    bl_idname = "regchk_main_guard.run"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}
