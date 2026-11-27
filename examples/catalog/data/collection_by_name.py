# /// catalog
# title = "`collection[\"name\"]`"
# section = "collections"
# status = "handled"
# safeguards = ["stub-generator"]
# features = ["api_types"]
# ///
"""A collection of Blender data is looked up by name or by index, and both give its element type: an `Object` from
`bpy.data.objects`. Whether the name exists is known only while Blender runs, so a lookup of a missing name is not
reported; `.get()` is the form that can say so."""

# catalog: hide
from typing import assert_type

# catalog: show
import bpy
from bpy.types import Object


def example() -> None:
    assert_type(bpy.data.objects["Cube"], Object)
    assert_type(bpy.data.objects[0], Object)
