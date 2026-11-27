# /// catalog
# title = "Vector properties and their subtype"
# section = "value-types"
# status = "handled"
# handled-by = ["typechecker"]
# features = ["properties"]
# ///
"""A `FloatVectorProperty` gives a `mathutils` type chosen by its `subtype` and `size`: `Color` for a colour of size
3, `Vector` for a translation or direction, `Euler` and `Quaternion` for rotations, `Matrix` for a `MATRIX` of size
(4, 4) or 16. Any other subtype or size gives an array of floats."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.props import FloatVectorProperty
from bpy.types import PropertyGroup, bpy_prop_array
from mathutils import Color, Euler, Matrix, Vector


class Transform(PropertyGroup):
    tint: FloatVectorProperty(subtype="COLOR", size=3)
    offset: FloatVectorProperty(subtype="TRANSLATION")
    rotation: FloatVectorProperty(subtype="EULER", size=3)
    space: FloatVectorProperty(subtype="MATRIX", size=(4, 4))
    weights: FloatVectorProperty(size=5)


def example(transform: Transform) -> None:
    assert_type(transform.tint, Color)
    assert_type(transform.offset, Vector)
    assert_type(transform.rotation, Euler)
    assert_type(transform.space, Matrix)
    assert_type(transform.weights, bpy_prop_array[float])
