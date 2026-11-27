# /// catalog
# title = "Pointers to a group and to a data-block"
# section = "value-types"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["properties"]
# ///
"""A `PointerProperty` to a `PropertyGroup` always holds an instance of it: Blender creates it with its owner, and it
cannot be replaced. A pointer to a data-block type (`Object`, `Material`, ...) is `None` until it is set."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.props import FloatProperty, PointerProperty
from bpy.types import Object, PropertyGroup


class Margins(PropertyGroup):
    top: FloatProperty()


class Layout(PropertyGroup):
    margins: PointerProperty(type=Margins)
    target: PointerProperty(type=Object)


def example(layout: Layout) -> None:
    assert_type(layout.margins, Margins)
    assert_type(layout.target, Object | None)
