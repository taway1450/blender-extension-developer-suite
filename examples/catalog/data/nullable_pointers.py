# /// catalog
# title = "Pointers `None` until set"
# section = "pointers"
# status = "handled"
# safeguards = ["stub-generator"]
# features = ["api_types"]
# ///
"""Some data is created only on demand: an object has no `animation_data` until it is animated or
`animation_data_create()` is called. The stubs type such a pointer as `X | None`, so a read through it is reported until
the code checks it or creates the data."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import AnimData, Object


def example(ob: Object) -> None:
    print(ob.animation_data.action)  # ty: ignore[missing-union-attribute]
    if ob.animation_data is None:
        assert_type(ob.animation_data_create(), AnimData)
