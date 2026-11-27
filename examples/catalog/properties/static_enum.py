# /// catalog
# title = "Enum properties with static items"
# section = "value-types"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["properties"]
# ///
"""An `EnumProperty` with a literal `items` sequence gives a `Literal` of its identifiers, so a typo in a comparison or
a write is reported. With `options={"ENUM_FLAG"}` the value is a `set` of them."""

# catalog: hide
from typing import Literal, assert_type

# catalog: show
from bpy.props import EnumProperty
from bpy.types import PropertyGroup

AXES = [("X", "X", ""), ("Y", "Y", ""), ("Z", "Z", "")]


class Settings(PropertyGroup):
    axis: EnumProperty(items=AXES)
    locked: EnumProperty(items=AXES, options={"ENUM_FLAG"})


def example(settings: Settings) -> None:
    assert_type(settings.axis, Literal["X", "Y", "Z"])
    assert_type(settings.locked, set[Literal["X", "Y", "Z"]])
    settings.axis = "W"  # ty: ignore[invalid-assignment]
