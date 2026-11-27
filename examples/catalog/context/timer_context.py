# /// catalog
# title = "`bpy.context` in a timer"
# section = "outside-callbacks"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["assumptions"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs type `context.object` as `Object`, without `None`."
# ///
"""A function given to `bpy.app.timers.register` runs later, outside any callback. `bpy.context.scene` there is the
scene of the first window, so in ordinary use it is set, but nothing guarantees it. The checker takes it as set and
reports the read as an Assumption. Other members, such as `object`, keep `X | None`."""

# catalog: hide
from typing import assert_type

# catalog: show
import bpy
from bpy.types import Object


def autosave_frame() -> float | None:
    print(bpy.context.scene.frame_current)  # ty: ignore[blender-assumed-context-member]
    assert_type(bpy.context.object, Object | None)
    return 10.0


def register() -> None:
    bpy.app.timers.register(autosave_frame, first_interval=10.0)
