# /// catalog  # ty: ignore[blender-invalid-register]
# title = "`register()` without `unregister()`"
# section = "entry-points"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["addon_discovery"]
#
# [evidence]
# addon = "addon_discovery/disc_no_unregister"
# register = "fails"
# says = "unregister(), which does not exist"
# ///
"""Blender calls `register()` when the add-on is enabled and `unregister()` when it is disabled; an add-on without
one of them cannot be enabled. The checker reports the missing function on the first line of `__init__.py`."""

import bpy
from bpy.props import IntProperty


def register():
    bpy.types.Scene.marker = IntProperty()
