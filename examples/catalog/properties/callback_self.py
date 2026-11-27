# /// catalog
# title = "`self` in property callbacks"
# section = "callbacks"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["properties"]
# ///
"""Blender calls a property's `update`, `get`, `set`, `poll` and `items` callbacks with the instance that holds the
property as `self`, though they are plain functions. The checker knows which class that is: a lambda's `self` is the
declaring class, and a function whose `self` is annotated with another class is reported where it is passed."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.props import FloatProperty, StringProperty
from bpy.types import Context, Object, PropertyGroup


def clamp_ratio(self: "Settings", context: Context) -> None:
    if self.ratio > self.limit:
        self.ratio = self.limit


def rename_object(self: Object, context: Context) -> None:
    self.name = "Settings changed"


class Settings(PropertyGroup):
    limit: FloatProperty(default=1.0)
    ratio: FloatProperty(update=clamp_ratio)
    label: StringProperty(get=lambda self: f"{assert_type(self, Settings).ratio:.0%}")
    other: FloatProperty(update=rename_object)  # ty: ignore[invalid-argument-type]
