"""Hover shows the bl_space_type subclass kept for a panel opened as a popover."""

from . import NAR_POPOVER_PT_settings


class _Settings(NAR_POPOVER_PT_settings):
    def draw(self, context):
        context.space_data
        #       ^hover-contains "SpaceView3D"
