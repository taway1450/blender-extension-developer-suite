# /// catalog
# title = "The class attribute of a declared property"
# section = "registered"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["properties"]
# ///
"""A declared property exists on instances only. Once the class is registered, `Settings.count` raises
`AttributeError`: registration has turned the annotation into an RNA property. The checker reports the read."""

from bpy.props import IntProperty
from bpy.types import PropertyGroup


class Settings(PropertyGroup):
    count: IntProperty()


def default_count() -> int:
    return Settings.count  # ty: ignore[missing-attribute]
