# /// catalog
# title = "Never-None pointers"
# section = "pointers"
# status = "handled"
# safeguards = ["stub-generator"]
# features = ["api_types"]
# see = ["blender/source/blender/makesrna/intern/makesrna.cc"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs type these pointers as `X | None`: they do not carry which pointers are never `None`."
# "fake-bpy-module/5.2" = "These stubs type these pointers as `X | None`: they do not carry which pointers are never `None`."
# ///
"""The stubs type a pointer that can never be `None` without `None`, so it is read directly. `camera.dof` is such a
pointer: Blender stores the struct inside the camera, so there is always one. A pointer that can be `None`, such as
`object.pose`, keeps it."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import Camera, CameraDOFSettings, Object, Pose


def example(camera: Camera, ob: Object) -> None:
    assert_type(camera.dof, CameraDOFSettings)
    assert_type(ob.pose, Pose | None)
