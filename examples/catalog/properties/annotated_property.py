# /// catalog
# title = "A property declared as an annotation"
# section = "declaring"
# status = "handled"
# handled-by = ["typechecker"]
# features = ["properties"]
# ///
"""A Property host declares its properties as class annotations, `name: IntProperty(...)`. The annotation is a call,
which the typing spec rejects, but the checker reads it as a declaration: the attribute has the property's Value
type on every instance."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.props import IntProperty
from bpy.types import PropertyGroup


class Settings(PropertyGroup):
    count: IntProperty(default=2, min=0)


# catalog: hide
def _(settings: Settings) -> None:
    # catalog: show
    assert_type(settings.count, int)
    settings.count = "two"  # ty: ignore[invalid-assignment]
