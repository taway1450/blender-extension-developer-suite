# /// catalog
# title = "`.get()`"
# section = "collections"
# status = "handled"
# safeguards = ["stub-generator"]
# features = ["api_types"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs type `.get()` as returning a plain `bpy_struct`, which has no `name`."
# ///
"""`collection.get(name)` gives the element, or `None` when there is none of that name. The stubs type it as `X | None`,
so a read without a check is reported."""

# catalog: hide
from typing import assert_type

# catalog: show
import bpy
from bpy.types import Material


def example() -> None:
    assert_type(bpy.data.materials.get("Rust"), Material | None)
    print(bpy.data.materials.get("Rust").name)  # ty: ignore[missing-union-attribute]
