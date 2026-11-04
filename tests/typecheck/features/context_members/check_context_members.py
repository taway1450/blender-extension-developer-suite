"""Expected types of bpy.context members.

Context members depend on where the context comes from (window, area, operator). The assertions
describe the members as an operator's execute() sees them in the 3D viewport, with an open file.
"""

from __future__ import annotations

from typing import assert_type

import bpy
from bpy.types import (Area, BlendData, Collection, Context, Object, Preferences, Scene, ViewLayer, Window,
                       WindowManager)


def context_members(context: Context) -> None:
    assert_type(context.scene, Scene)
    assert_type(context.view_layer, ViewLayer)
    assert_type(context.collection, Collection)
    assert_type(context.blend_data, BlendData)
    assert_type(context.preferences, Preferences)
    assert_type(context.window_manager, WindowManager)
    assert_type(context.window, Window | None)
    assert_type(context.area, Area | None)
    mode: str = context.mode  # an enum: the stubs may use a Literal union, which must still be a str
    assert_type(context.active_object, Object | None)
    assert_type(context.object, Object | None)
    assert_type(context.selected_objects, list[Object])


def module_level() -> None:
    assert_type(bpy.context, Context)
    assert_type(bpy.data, BlendData)


def temp_override(context: Context, area: Area) -> None:
    with context.temp_override(area=area):
        pass
    with context.temp_override(area=area, active_object=None):
        pass
    context.temp_override(area=1)  # ty: ignore[invalid-argument-type]


def unknown_member(context: Context) -> None:
    context.active_objekt  # ty: ignore[unresolved-attribute]
