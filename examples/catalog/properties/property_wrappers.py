# /// catalog
# title = "Constants, `partial` and wrapper functions"
# section = "callbacks"
# status = "handled"
# handled-by = ["typechecker"]
# features = ["property_wrappers"]
# ///
"""Add-ons share declarations: a module constant, `functools.partial`, a small function that returns a property. The
checker evaluates the annotation as a value, so each gives the Value type of the call it stands for."""

# catalog: hide
from typing import assert_type

# catalog: show
from functools import partial

from bpy.props import FloatProperty, IntProperty
from bpy.types import PropertyGroup

OPACITY = FloatProperty(min=0.0, max=1.0)
Percent = partial(IntProperty, min=0, max=100, subtype="PERCENTAGE")


def distance(name: str):
    return FloatProperty(name=name, subtype="DISTANCE")


class Style(PropertyGroup):
    opacity: OPACITY
    fill: Percent()
    margin: distance("Margin")


def example(style: Style) -> None:
    assert_type(style.opacity, float)
    assert_type(style.fill, int)
    assert_type(style.margin, float)
