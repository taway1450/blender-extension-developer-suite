# /// catalog
# title = "Reloading with `importlib.reload`"
# section = "entry-points"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["registration"]
# see = ["blender/scripts/modules/addon_utils.py"]
# ///
"""When an add-on's file changed on disk, Blender re-enables it with `importlib.reload`, which runs the module again
in its old namespace: `"bpy" in locals()` is true only then, and the submodules imported on the first run are still
bound. So the guard can use `ops` before the line that imports it; the checker reads the guard the same way and
does not report `ops` as unresolved."""

# catalog: hide
from typing import Literal, assert_type

# catalog: show
if "bpy" in locals():
    import importlib

    assert_type(ops.LABEL, Literal["Run"])
    importlib.reload(ops)

import bpy

from . import ops


def register():
    ops.register()


def unregister():
    ops.unregister()
