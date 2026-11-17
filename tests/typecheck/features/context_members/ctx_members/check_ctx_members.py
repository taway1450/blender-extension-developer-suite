"""Outside a callback Blender guarantees nothing: a helper may get a restricted or overridden context, and at module
level (while the add-on is imported) bpy.context is a restricted one. `scene`, `view_layer` and `tool_settings` are
taken as not None there all the same, as an Assumption (features/assumptions/asm_context_member); `blend_data` keeps
the stub type."""

from __future__ import annotations

from typing import assert_type

import bpy
from bpy.types import BlendData, Context


def helper(context: Context) -> None:
    assert_type(context.blend_data, BlendData | None)  # bare-ok: a helper is no callback
    assert_type(bpy.context.blend_data, BlendData | None)  # bare-ok: a helper is no callback


assert_type(bpy.context.blend_data, BlendData | None)  # bare-ok: module level is no callback
