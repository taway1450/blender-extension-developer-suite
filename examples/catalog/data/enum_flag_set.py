# /// catalog
# title = "An enum-flag set"
# section = "enums"
# status = "handled"
# safeguards = ["stub-generator"]
# features = ["api_types"]
# ///
"""An enum-flag property holds a set of identifiers, such as an operator's `bl_options`. The stubs type it as a set of
the `Literal` identifiers, so a misspelt one is reported."""

from bpy.types import Operator


class Nudge(Operator):
    bl_idname = "data.nudge"
    bl_label = "Nudge"
    bl_options = {"REGISTER", "UNDOO"}  # ty: ignore[invalid-assignment]
