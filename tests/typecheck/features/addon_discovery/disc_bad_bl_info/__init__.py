"""Feature test: a legacy add-on with a malformed bl_info."""

bl_info = {  # ty: ignore[blender-invalid-addon-metadata]
    "version": (1, 0, 0),
    "blender": "4.2",  # ty: ignore[blender-invalid-addon-metadata]
    "category": "Development",
}
# "name" is missing (reported on the dict) and "blender" must be a tuple of three ints.


def register():
    pass


def unregister():
    pass
