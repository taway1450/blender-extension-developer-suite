# /// catalog
# title = "A BMesh layer by name"
# section = "math-mesh"
# status = "partial"
# safeguards = ["stub-generator"]
# features = ["api_types"]
# note = "`.get()` is typed loosely in the stubs, so a layer used without a check is not reported."
#
# [future]
# class = "possible"
# note = "Type `.get()` on a BMesh layer collection as `BMLayerItem | None` in the stubs."
#
# [differs]
# "fake-bpy-module/main" = "fake-bpy-module types a new BMesh layer as `Any`."
# "fake-bpy-module/5.2" = "These stubs type a new BMesh layer as `Any`."
# ///
"""A BMesh keeps extra per-element data in layers, found by name: `bm.verts.layers.float.get("weight")` is the layer, or
`None` when there is none, and `.new("weight")` creates it. The stubs type a new layer, but not the `None` of `.get()`,
so a layer used without a check is not reported; the marked line shows the result a check would give."""

# catalog: hide
from typing import assert_type

# catalog: show
from bmesh.types import BMesh, BMLayerItem


def example(bm: BMesh) -> None:
    assert_type(bm.verts.layers.float.new("weight"), BMLayerItem)
    # gap: the `None` of `.get()` is not typed
    print(bm.verts.layers.float.get("weight").name)  # ty: ignore[missing-union-attribute]
