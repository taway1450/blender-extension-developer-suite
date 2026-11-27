# /// catalog
# title = "`bpy.data` during registration"
# section = "restricted"
# status = "not-handled"
# see = ["blender/scripts/modules/_bpy_restrict_state.py", "blender/scripts/modules/addon_utils.py"]
#
# [future]
# class = "possible"
# note = "The add-on typechecker could report a read of `bpy.data` at module level and in `register()`, as it reports `bpy.context` members there."
# ///
"""While Blender imports an add-on and runs its `register()`, `bpy.data` is an empty stand-in, so reading any
collection raises `AttributeError` and the add-on fails to enable. Read the data in a callback, a handler or a timer
instead. The checker does not tell `register()` from other code; the marked line shows the result a check would
give."""

import bpy

bl_info = {
    "name": "Catalog: bpy.data during registration",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


def register():
    # gap: `bpy.data` is not known to be empty here
    print(len(bpy.data.objects))  # ty: ignore[missing-attribute]


def unregister():
    pass
