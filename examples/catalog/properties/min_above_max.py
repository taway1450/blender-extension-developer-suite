# /// catalog
# title = "A minimum above the maximum"
# section = "callbacks"
# status = "not-handled"
# features = ["properties"]
#
# [future]
# class = "possible"
# note = "Compare literal `min` and `max` (and `soft_min` and `soft_max`) in `blender-invalid-property`."
#
# [runtime]
# register = "ok"
#
# [[runtime.probe]]
# code = "addon.MIN_ABOVE_MAX_Settings.bl_rna.properties['level'].hard_min"
# expect = 10
# reason = "Blender keeps the minimum as given"
# ///
"""Blender rejects many wrong `bpy.props` arguments at registration, but not a `min` above `max`: the class registers
and the property keeps both limits, so no value is in range. Nothing reports it yet."""

import bpy
from bpy.props import IntProperty
from bpy.types import PropertyGroup

bl_info = {
    "name": "Catalog: a minimum above the maximum",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


class MIN_ABOVE_MAX_Settings(PropertyGroup):
    # gap: the limits are not compared
    level: IntProperty(min=10, max=0)  # ty: ignore[blender-invalid-property]


def register():
    bpy.utils.register_class(MIN_ABOVE_MAX_Settings)


def unregister():
    bpy.utils.unregister_class(MIN_ABOVE_MAX_Settings)
