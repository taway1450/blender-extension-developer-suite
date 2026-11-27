# /// catalog
# title = "Property arguments are keyword-only"
# section = "declaring"
# status = "handled"
# safeguards = ["stub-generator"]
# features = ["properties"]
# ///
"""Every argument of the `bpy.props` functions is keyword-only, so `StringProperty("Name")` raises `TypeError`. The
stubs say so, and any type checker reports it."""

from bpy.props import StringProperty
from bpy.types import PropertyGroup


class Settings(PropertyGroup):
    name_ok: StringProperty(name="Name")
    name_wrong: StringProperty("Name")  # ty: ignore[too-many-positional-arguments]
