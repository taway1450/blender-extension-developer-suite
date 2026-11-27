# /// catalog
# title = "Scalar Value types"
# section = "value-types"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["properties"]
# ///
"""`IntProperty`, `FloatProperty`, `BoolProperty` and `StringProperty` give `int`, `float`, `bool` and `str`. A string
with `subtype="BYTE_STRING"` gives `bytes`. A write of another type is an error."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.props import BoolProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import PropertyGroup


class Settings(PropertyGroup):
    count: IntProperty()
    ratio: FloatProperty()
    enabled: BoolProperty()
    label: StringProperty()
    raw: StringProperty(subtype="BYTE_STRING")


def example(settings: Settings) -> None:
    assert_type(settings.count, int)
    assert_type(settings.ratio, float)
    assert_type(settings.enabled, bool)
    assert_type(settings.label, str)
    assert_type(settings.raw, bytes)
    settings.ratio = 1  # an int is a float
    settings.count = 1.5  # ty: ignore[invalid-assignment]
