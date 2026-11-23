"""Hover shows a Grease Pencil brush's settings as never None."""

from . import PTR_BRUSH_PT_draw


class _Draw(PTR_BRUSH_PT_draw):
    def draw(self, context):
        context.tool_settings.gpencil_paint.brush.gpencil_settings
        #                                         ^hover
