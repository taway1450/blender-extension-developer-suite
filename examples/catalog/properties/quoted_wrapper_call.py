# /// catalog
# title = "A wrapper call in a quoted annotation"
# section = "callbacks"
# status = "not-handled"
# features = ["property_wrappers"]
#
# [future]
# class = "possible"
# note = "Evaluate a string annotation that holds a call as the call, as Blender does when it registers the class."
# ///
"""Blender evaluates a string annotation when it registers the class, so `size: "distance('Size')"` declares a
property like the unquoted call. The checker parses the string as a type expression instead, and does not read the
call."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.props import FloatProperty
from bpy.types import PropertyGroup


def distance(name: str):
    return FloatProperty(name=name, subtype="DISTANCE")


class Shape(PropertyGroup):
    # gap: reported as a call in a type expression
    size: "distance('Size')"


def example(shape: Shape) -> None:
    # gap: the quoted call is not read as a declaration
    assert_type(shape.size, float)
