"""Feature test: inside `with context.temp_override(k=v, ...)`, context.k is v.

Context.temp_override puts the keyword arguments in front of the context's own members until the block ends
(bpy_rna_context.cc), so a member passed is read back as the value passed, also through bpy.context. Outside the block
the member is what it was, and so it is in the block once the context variable is rebound. This is the code's own
control flow, so it is not reported.

The assert_type calls in the bodies are no-ops at runtime."""

from typing import assert_type

import bpy
from bpy.types import Area, Context, Object, Operator, Region, Window


def redraw(window: Window, area: Area) -> None:
    region = [region for region in area.regions if region.type == "WINDOW"][0]
    with bpy.context.temp_override(window=window, area=area, region=region):
        assert_type(bpy.context.region, Region)  # oracle-skip: the member temp_override passed
        bpy.context.region.tag_redraw()
        assert_type(bpy.context.area, Area)  # oracle-skip: the member temp_override passed
        assert_type(bpy.context.window, Window)  # oracle-skip: the member temp_override passed
        assert_type(bpy.context.screen, bpy.types.Screen | None)  # bare-ok: not passed
    assert_type(bpy.context.region, Region | None)  # bare-ok: outside the block


def rebound(context: Context, area: Area, other: Context) -> None:
    with context.temp_override(area=area):
        assert_type(context.area, Area)  # oracle-skip: the member temp_override passed
        context = other
        assert_type(context.area, Area | None)  # bare-ok: `context` was rebound in the block


class CTX_OVERRIDE_OT_object(Operator):
    bl_idname = "ctx_override.object"
    bl_label = "Override"

    def execute(self, context):
        target = bpy.data.objects[0]
        with context.temp_override(active_object=target, object=target):
            assert_type(context.active_object, Object)  # oracle-skip: the member temp_override passed
            assert_type(context.object, Object)  # oracle-skip: the member temp_override passed
            assert_type(context.material, bpy.types.Material | None)  # bare-ok: not passed
        context.active_object.name  # ty: ignore[missing-union-attribute]  # bare-ok: outside the block
        return {"FINISHED"}


classes = (CTX_OVERRIDE_OT_object,)
register, unregister = bpy.utils.register_classes_factory(classes)
