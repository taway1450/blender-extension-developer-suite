# /// catalog
# title = "The old `x = IntProperty()` form"
# section = "declaring"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["properties"]
# ///
"""Before Blender 2.80 properties were class attributes, `count = IntProperty()`. Blender now ignores that form
without a word: the class registers, but has no such property. The checker reports the assignment, so it is not
mistaken for a declaration."""

from bpy.props import IntProperty
from bpy.types import PropertyGroup


class Settings(PropertyGroup):
    count = IntProperty()  # ty: ignore[blender-legacy-property]
    total: IntProperty()
