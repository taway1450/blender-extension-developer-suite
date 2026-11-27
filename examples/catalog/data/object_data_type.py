# /// catalog
# title = "`object.data` by type"
# section = "pointers"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["type_narrowing"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs type `object.data` as `ID | None`, with no view of `data` per `type` for the checker to narrow to."
# "fake-bpy-module/5.2" = "These stubs have no view of `object.data` per `type`, so it stays the union of all data types."
# ///
"""After a test of `object.type`, in an `if` or a `match`, the checker narrows `object.data` to the data-block that type
holds: a `Mesh` for `"MESH"`. The stubs type `data` as the union of every kind of data-block, and `None` for an empty."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import Camera, Mesh, Object


def example(ob: Object) -> None:
    if ob.type == "MESH":
        assert_type(ob.data, Mesh)
    match ob.type:
        case "CAMERA":
            assert_type(ob.data, Camera)
