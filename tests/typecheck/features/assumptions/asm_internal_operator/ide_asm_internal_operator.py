"""Hover shows a context member of an Internal operator taken as set (here in a test, which is not reported)."""

from bpy.types import Operator


class ASM_INTERNAL_OPERATOR_OT_hover(Operator):
    bl_idname = "asm_internal_operator.hover"
    bl_label = "Hover"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        if context.screen is None:
            #      ^hover
            return {'CANCELLED'}
        return {'FINISHED'}
