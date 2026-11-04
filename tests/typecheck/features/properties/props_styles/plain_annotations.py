"""Annotations without `from __future__ import annotations`: evaluated when the class is created."""

from bpy.props import BoolProperty, IntProperty
from bpy.types import PropertyGroup


class PROPS_STYLES_Plain(PropertyGroup):
    count: IntProperty()
    quoted: "BoolProperty()"  # a string annotation: Blender evaluates it at registration
    legacy = IntProperty()  # ty: ignore[blender-legacy-property]
    # Before Blender 2.80 properties were class attributes. Since then they are ignored: no property is made.


classes = (PROPS_STYLES_Plain,)
