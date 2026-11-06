"""Outside a callback Blender guarantees nothing: a helper may get a restricted or overridden context, and at module
level (while the add-on is imported) bpy.context is a restricted one."""

from __future__ import annotations

from typing import assert_type

import bpy
from bpy.types import BlendData, Context, Scene, ToolSettings, ViewLayer


def helper(context: Context) -> None:
    assert_type(context.scene, Scene | None)  # bare-ok: a helper is no callback
    assert_type(context.view_layer, ViewLayer | None)  # bare-ok: a helper is no callback
    assert_type(context.tool_settings, ToolSettings | None)  # bare-ok: a helper is no callback
    assert_type(bpy.context.blend_data, BlendData | None)  # bare-ok: a helper is no callback


assert_type(bpy.context.scene, Scene | None)  # bare-ok: module level is no callback
