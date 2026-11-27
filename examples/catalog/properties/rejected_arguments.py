# /// catalog
# title = "Arguments Blender rejects at registration"
# section = "declaring"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["properties"]
# evidence = "properties/props_defaults"
# ///
"""Some `bpy.props` arguments type-check against the stubs but make `register_class` raise `ValueError`: a default
that is not one of the enum's items, a `set` callback without `get`, a vector `size` above
32. The checker reports each where it is written."""

from bpy.props import EnumProperty, FloatVectorProperty, IntProperty
from bpy.types import PropertyGroup

MODES = [("FAST", "Fast", ""), ("EXACT", "Exact", "")]


def set_level(self, value: int) -> None:
    pass


class Settings(PropertyGroup):
    mode: EnumProperty(items=MODES, default="SLOW")  # ty: ignore[blender-invalid-property]
    level: IntProperty(set=set_level)  # ty: ignore[blender-invalid-property]
    weights: FloatVectorProperty(size=40)  # ty: ignore[blender-invalid-property]
