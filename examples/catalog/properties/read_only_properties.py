# /// catalog
# title = "Read-only properties"
# section = "value-types"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["properties"]
#
# [evidence]
# addon = "properties/generated/props_scalar"
# says = "a READ_ONLY property cannot be written"
# ///
"""A property declared with `options={"READ_ONLY"}` can be read but not assigned: Blender raises `AttributeError` on
a write. The checker reads the option, keeps the Value type for reading, and reports an assignment; it takes a
property with a `get` callback and no `set` as read-only too."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.props import IntProperty
from bpy.types import PropertyGroup


def get_total(self: "Settings") -> int:
    return 3


class Settings(PropertyGroup):
    fixed: IntProperty(options={"READ_ONLY"})
    total: IntProperty(get=get_total)


def example(settings: Settings) -> None:
    assert_type(settings.fixed, int)
    settings.fixed = 1  # ty: ignore[invalid-assignment]
    settings.total = 1  # ty: ignore[invalid-assignment]
