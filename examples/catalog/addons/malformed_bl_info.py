# /// catalog
# title = "A malformed `bl_info`"
# section = "metadata"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["addon_discovery"]
# ///
"""A legacy add-on describes itself in `bl_info`: `name` is required and `blender` is a tuple of three ints. The
checker reports a missing key on the dict and a wrong value on its entry."""

bl_info = {  # ty: ignore[blender-invalid-addon-metadata]
    "version": (1, 0, 0),
    "blender": "4.2",  # ty: ignore[blender-invalid-addon-metadata]
    "category": "Development",
}


def register():
    pass


def unregister():
    pass
