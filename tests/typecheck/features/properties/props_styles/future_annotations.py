"""Annotations with `from __future__ import annotations`: strings, evaluated by Blender at registration, so a
PointerProperty can name a class that is defined further down."""

from __future__ import annotations

from bpy.props import FloatProperty, PointerProperty
from bpy.types import PropertyGroup


class PROPS_STYLES_Future(PropertyGroup):
    later: PointerProperty(type=PROPS_STYLES_Later)
    factor: FloatProperty()


class PROPS_STYLES_Later(PropertyGroup):
    ratio: FloatProperty()


classes = (PROPS_STYLES_Later, PROPS_STYLES_Future)
