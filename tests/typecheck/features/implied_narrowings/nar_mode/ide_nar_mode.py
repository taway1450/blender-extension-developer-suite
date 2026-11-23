"""Hover shows what a poll's `context.mode` check narrows a read to."""

from . import NAR_MODE_OT_pose, NAR_MODE_PT_sculpt


class _Sculpt(NAR_MODE_PT_sculpt):
    def draw(self, context):
        context.tool_settings.sculpt
        #                     ^hover


class _Pose(NAR_MODE_OT_pose):
    def execute(self, context):
        context.object.pose
        #              ^hover
        return {"FINISHED"}
