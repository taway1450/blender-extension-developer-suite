# /// catalog
# title = "`foreach_get`"
# section = "collections"
# status = "partial"
# safeguards = ["stub-generator"]
# features = ["api_types"]
# note = "The attribute name is a plain `str`: a misspelt one is not reported."
#
# [future]
# class = "possible"
# note = "Check the attribute name against the element type's properties."
# ///
"""`collection.foreach_get(name, values)` reads one attribute of every element into a flat sequence in one call, much
faster than a loop. The stubs type the call, but the attribute name is a plain string, so a misspelt one is not
reported; the marked line shows the result a check would give."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import Mesh


def example(mesh: Mesh) -> None:
    coords = [0.0] * (len(mesh.vertices) * 3)
    assert_type(mesh.vertices.foreach_get("co", coords), None)
    # gap: the attribute name is not checked
    mesh.vertices.foreach_get("coo", coords)  # ty: ignore[invalid-argument-type]
