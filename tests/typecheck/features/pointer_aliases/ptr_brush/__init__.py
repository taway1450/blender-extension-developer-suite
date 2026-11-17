"""Feature test: a Grease Pencil mode's brush has Grease Pencil settings once it is read (a Pointer alias).

The brush of a Grease Pencil paint mode (tool_settings.gpencil_paint, gpencil_sculpt_paint, gpencil_weight_paint,
gpencil_vertex_paint) is a brush of that mode: Paint.brush is read-only, and BKE_paint_brush_set only accepts a brush
whose ob_mode has the paint's mode (BKE_paint_can_use_brush). BKE_brush_add allocates gpencil_settings for the four
Grease Pencil modes, bpy.data.brushes.new() for every brush, and entering Grease Pencil draw mode ensures them for its
brush. So <gp paint>.brush.gpencil_settings is not None wherever the brush itself is set, with or without a poll.

The assert_type calls in the bodies are no-ops at runtime."""

from typing import assert_type

import bpy
from bpy.types import BrushGpencilSettings, Panel


class PTR_BRUSH_PT_draw(Panel):
    bl_label = "Draw brush"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Aliases"

    @classmethod
    def poll(cls, context):
        paint = context.tool_settings.gpencil_paint
        return paint is not None and paint.brush is not None

    def draw(self, context):
        brush = context.tool_settings.gpencil_paint.brush  # ty: ignore[blender-narrowed-by-poll]
        assert_type(brush.gpencil_settings, BrushGpencilSettings)  # oracle-skip: a Pointer alias, silent
        settings = brush.gpencil_settings
        self.layout.prop(settings, "pen_strength")


class PTR_BRUSH_PT_sculpt(Panel):
    """No poll: the draw's own test makes the brush set."""

    bl_label = "Sculpt brush"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Aliases"

    def draw(self, context):
        paint = context.tool_settings.gpencil_weight_paint
        if paint is not None and paint.brush is not None:
            assert_type(paint.brush.gpencil_settings, BrushGpencilSettings)  # oracle-skip: a Pointer alias, silent
        vertex = context.tool_settings.gpencil_vertex_paint
        if vertex is not None and vertex.brush is not None:
            assert_type(vertex.brush.gpencil_settings, BrushGpencilSettings)  # oracle-skip: a Pointer alias, silent
        sculpt = context.tool_settings.sculpt
        if sculpt is not None and sculpt.brush is not None:
            assert_type(sculpt.brush.gpencil_settings, BrushGpencilSettings | None)  # bare-ok: a sculpt brush may have none


classes = (PTR_BRUSH_PT_draw, PTR_BRUSH_PT_sculpt)
register, unregister = bpy.utils.register_classes_factory(classes)
