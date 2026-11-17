"""Hover shows the type a poll() check narrows a read to."""

from . import NAR_POLL_OT_helpers, NAR_POLL_PT_conjuncts


class _Conjuncts(NAR_POLL_PT_conjuncts):
    def draw(self, context):
        context.object
        #       ^hover


class _Helpers(NAR_POLL_OT_helpers):
    def execute(self, context):
        context.space_data
        #       ^hover-contains "SpaceNodeEditor"
        return {"FINISHED"}
