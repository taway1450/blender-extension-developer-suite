# /// catalog
# title = "`from __future__ import annotations`"
# section = "declaring"
# status = "handled"
# handled-by = ["typechecker"]
# features = ["properties"]
# ///
"""With `from __future__ import annotations` every annotation is a string, which Blender evaluates when it registers
the class. A `PointerProperty` can then name a class defined further down the module. The checker evaluates the
string the same way."""

from __future__ import annotations

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.props import FloatProperty, PointerProperty
from bpy.types import PropertyGroup


class Brush(PropertyGroup):
    falloff: PointerProperty(type=Falloff)


class Falloff(PropertyGroup):
    radius: FloatProperty(default=1.0)


def radius(brush: Brush) -> float:
    # catalog: hide
    assert_type(brush.falloff, Falloff)
    # catalog: show
    return brush.falloff.radius
