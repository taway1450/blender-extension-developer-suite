# /// catalog
# title = "An operator in a property callback"
# section = "threads"
# status = "not-handled"
# blender-docs = ["info_gotchas_crashes", "info_gotchas_operators"]
#
# [future]
# class = "not-checkable"
# note = "Whether the callback breaks undo or starts an update loop depends on what the operator does while Blender runs."
# ///
"""A property's `update` callback should be fast. Calling an operator there may work, but Blender's docs say it is not
supported: the operator and the property edit each store an undo step, and a callback that sets properties again can
loop. Change the data directly in the callback."""

import bpy
from bpy.props import BoolProperty
from bpy.types import Context, PropertyGroup


def select_everything(self: "Settings", context: Context) -> None:
    bpy.ops.object.select_all(action="SELECT")  # not supported in a callback


class Settings(PropertyGroup):
    select_all: BoolProperty(update=select_everything)
