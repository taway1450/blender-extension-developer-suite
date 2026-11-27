# /// catalog
# title = "Classes that take no Registered properties"
# section = "registered"
# status = "handled"
# handled-by = ["typechecker"]
# features = ["properties"]
# ///
"""Registered properties work on every data-block type and on bones, nodes, sockets, view layers and strips, but not
on `Area`, `Window`, `Modifier`, `Preferences`, `Context` or a `SpaceView3D`. The checker reports the assignment."""

import bpy
from bpy.props import BoolProperty


def register() -> None:
    bpy.types.Object.pinned = BoolProperty()
    bpy.types.Area.pinned = BoolProperty()  # ty: ignore[blender-unsupported-property-target]
