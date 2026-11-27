# /// catalog
# title = "Functions appended to Blender's menus and headers"
# section = "popovers"
# status = "handled"
# safeguards = ["stub-generator"]
# features = ["api_types"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs have no `VIEW3D_MT_object` in `bpy.types`, so `append` on it is reported."
# ///
"""`append` on one of Blender's menus or headers adds a draw function, which Blender calls with the menu as `self`.
The function is plain, outside any class, so nothing says what `self` is; annotate it with `Menu` (or `Header`) and
`self.layout` is a `UILayout`, and a misspelt layout call is reported."""

# catalog: hide
from typing import assert_type

# catalog: show
import bpy
from bpy.types import Context, Menu, UILayout


def draw_scatter(self: Menu, context: Context) -> None:
    assert_type(self.layout, UILayout)
    self.layout.separator()
    self.layout.opertor("object.select_all")  # ty: ignore[missing-attribute]


def register() -> None:
    bpy.types.VIEW3D_MT_object.append(draw_scatter)
