# /// catalog
# title = "`bpy.context` at import time"
# section = "outside-callbacks"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["assumptions"]
# see = ["blender/scripts/modules/_bpy_restrict_state.py"]
# ///
"""While Blender imports and registers an add-on, `bpy.context` is a restricted context with no `scene` at all:
reading it raises `AttributeError`. `register()` runs in that context too, so the read belongs in a callback, a
handler or a timer (see [`bpy.data` during registration](hazards.md#restricted-data)). The checker does not tell
import time from other code outside callbacks: it reports the read only as the Assumption it makes for `scene` there,
a warning."""

import bpy

bl_info = {
    "name": "Catalog: bpy.context at import time",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}

START = bpy.context.scene.frame_start  # ty: ignore[blender-assumed-context-member]


def register():
    pass


def unregister():
    pass
