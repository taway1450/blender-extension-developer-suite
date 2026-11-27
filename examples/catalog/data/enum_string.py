# /// catalog
# title = "An enum value as a string"
# section = "enums"
# status = "handled"
# safeguards = ["stub-generator"]
# features = ["api_types"]
# ///
"""An enum property of Blender's takes and gives one of its identifiers as a string. The stubs type it as the `Literal`
of those identifiers, so a misspelt value is reported."""

# catalog: hide
from typing import Literal, assert_type

# catalog: show
from bpy.types import Object


def example(ob: Object) -> None:
    ob.rotation_mode = "QUATERNION"
    ob.rotation_mode = "XZYY"  # ty: ignore[invalid-assignment]
    assert_type(ob.display_type, Literal["BOUNDS", "WIRE", "SOLID", "TEXTURED"])
