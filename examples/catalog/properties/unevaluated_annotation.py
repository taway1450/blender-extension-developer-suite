# /// catalog
# title = "An annotation the checker cannot evaluate"
# section = "callbacks"
# status = "partial"
# safeguards = ["typechecker"]
# features = ["property_wrappers"]
# note = "The attribute is `Any` instead of its Value type."
#
# [future]
# class = "possible"
# note = "Follow a declaration built in a loop or read from a registry, as far as its values are literals."
# ///
"""When the checker cannot tell what an annotation evaluates to (a declaration built in a loop and picked from a
dict), it does not report the annotation as an invalid type: the attribute is `Any`, so nothing on it is checked."""

# catalog: hide
from typing import Any, assert_type

# catalog: show
from bpy.props import FloatProperty, IntProperty
from bpy.types import PropertyGroup

KINDS = {}
for name, factory in (("count", IntProperty), ("ratio", FloatProperty)):
    KINDS[name] = factory()


class Settings(PropertyGroup):
    count: KINDS["count"]


def example(settings: Settings) -> None:
    assert_type(settings.count, Any)
    # gap: the Value type is not known
    assert_type(settings.count, int)
