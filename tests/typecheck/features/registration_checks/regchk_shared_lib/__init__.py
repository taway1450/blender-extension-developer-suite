"""Not an addon (no manifest, no bl_info): a library both isolation addons import. Only regchk_isolation_a calls
register_tool(), so only it has the operator."""

import bpy
from bpy.types import Operator


class REGCHK_SHARED_OT_tool(Operator):
    bl_idname = "regchk_shared.tool"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def register_tool():
    bpy.utils.register_class(REGCHK_SHARED_OT_tool)


def unregister_tool():
    bpy.utils.unregister_class(REGCHK_SHARED_OT_tool)
