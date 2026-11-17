"""Hover shows what a panel's bl_context narrows a read to."""

from . import NAR_BL_CONTEXT_PT_object, NAR_BL_CONTEXT_PT_posemode


class _Object(NAR_BL_CONTEXT_PT_object):
    def draw(self, context):
        context.object  # ty: ignore[blender-narrowed-by-bl-context]
        #       ^hover


class _Pose(NAR_BL_CONTEXT_PT_posemode):
    def draw(self, context):
        context.object.pose  # ty: ignore[blender-narrowed-by-bl-context]
        #              ^hover
