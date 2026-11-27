# /// catalog
# title = "`bmesh.from_edit_mesh`"
# section = "math-mesh"
# status = "handled"
# safeguards = ["stub-generator"]
# features = ["api_types"]
#
# [differs]
# "fake-bpy-module/main" = "fake-bpy-module types an item of a face's `loops` as `Any`."
# "builtin/5.2" = "Blender 5.2's builtin stubs do not make `BMVertSeq` and `BMFaceSeq` iterable, so the items are unknown."
# "fake-bpy-module/5.2" = "These stubs type an item of a face's `loops` as `Any`."
# ///
"""`bmesh.from_edit_mesh` gives the `BMesh` of a mesh in edit mode, whose vertices, edges and faces are typed sequences:
an item of `bm.verts` is a `BMVert`, of a face's `loops` a `BMLoop`. The stubs type them, so an attribute the
element does not have, such as a face's `co`, is reported."""

# catalog: hide
from typing import assert_type

# catalog: show
import bmesh
from bmesh.types import BMesh, BMLoop, BMVert
from bpy.types import Mesh


def example(mesh: Mesh) -> None:
    bm = bmesh.from_edit_mesh(mesh)
    assert_type(bm, BMesh)
    for vert in bm.verts:
        assert_type(vert, BMVert)
    for face in bm.faces:
        assert_type(face.loops[0], BMLoop)
        print(face.co)  # ty: ignore[missing-attribute]
    bmesh.update_edit_mesh(mesh)
