# /// catalog
# title = "Strings returned by dynamic enum items"
# section = "callbacks"
# status = "not-handled"
# features = ["properties"]
# blender-docs = ["bpy.props"]
#
# [future]
# class = "not-checkable"
# note = "Whether Python still holds the strings depends on what the callback built and kept while Blender runs."
# ///
"""Blender does not copy the strings an `items` callback returns. When Python frees them, the enum shows garbage or
Blender crashes, so the callback has to keep its list alive, for example in a module-level variable. Whether it does
is a question of object lifetimes, which no static check can answer."""

import bpy
from bpy.props import EnumProperty
from bpy.types import Context, PropertyGroup

_items_cache = []


def material_items(self, context: Context | None):
    _items_cache[:] = [(m.name, m.name, "") for m in bpy.data.materials]
    return _items_cache


class Settings(PropertyGroup):
    material: EnumProperty(items=material_items)
