# /// catalog
# title = "Writing a vector property"
# section = "value-types"
# status = "handled"
# safeguards = ["typechecker", "stub-generator"]
# features = ["properties", "api_types"]
#
# [evidence]
# addon = "api_types/api_setters"
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs type `Object.location` as `Vector` for writes too, so assigning a tuple is reported."
# ///
"""A vector property reads as a `mathutils` object or an array, but takes any sequence of the right element type: a
tuple or a list, of rows for a `Matrix`. The checker types an add-on's own vector properties so, and the stubs
type Blender's (`Object.location`, `Light.color`) the same way. An element of the wrong type is still reported."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.props import FloatVectorProperty
from bpy.types import Object, PropertyGroup
from mathutils import Color, Vector


class Settings(PropertyGroup):
    tint: FloatVectorProperty(subtype="COLOR")


def example(settings: Settings, ob: Object) -> None:
    settings.tint = (1.0, 0.5, 0.0)
    assert_type(settings.tint, Color)
    ob.location = (1, 2, 3)
    assert_type(ob.location, Vector)
    ob.location = ("1", 2, 3)  # ty: ignore[invalid-assignment]
