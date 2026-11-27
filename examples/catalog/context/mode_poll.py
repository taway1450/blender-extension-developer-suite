# /// catalog
# title = "A poll that checks the mode"
# section = "narrowings"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["implied_narrowings"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's stubs type the callback's `context` as `Context | None`, so the poll's check is not read and `edit_object` is not narrowed."
# "fake-bpy-module/5.2" = "These stubs type the callback's `context` as `Context | None`, so the poll's check is not read and `edit_object` is not narrowed."
# ///
"""`context.mode == "EDIT_MESH"` in a poll says more than the mode: there is an object in edit mode, and it is a
mesh. The checker gives the callbacks the poll gates what the mode implies, `context.edit_object` set and its `data`
a `Mesh`, and reports the read as an Implied narrowing."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import Mesh, Operator


class Flatten(Operator):
    bl_idname = "context.flatten"
    bl_label = "Flatten"

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        assert_type(context.edit_object.data, Mesh)  # ty: ignore[blender-narrowed-by-poll]
        return {"FINISHED"}
