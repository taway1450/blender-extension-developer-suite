# /// catalog
# title = "Properties declared on a mixin"
# section = "declaring"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["properties"]
# ///
"""Annotations of a base class, and of a mixin that is no Blender class at all, become properties of every class that
derives from them. A subclass can replace one by declaring the name again."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.props import FloatProperty, IntProperty, StringProperty
from bpy.types import PropertyGroup


class Labelled:
    label: StringProperty()


class Item(Labelled, PropertyGroup):
    weight: FloatProperty()


class Counted(Item):
    weight: IntProperty()


def example(item: Item, counted: Counted) -> None:
    assert_type(item.label, str)
    assert_type(item.weight, float)
    assert_type(counted.weight, int)
