# /// catalog
# title = "`context.object` after a poll"
# section = "members"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["implied_narrowings"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's stubs type the callback's `context` as `Context | None`, so the poll's check is not read and every read of `context` is reported."
# "fake-bpy-module/5.2" = "These stubs type the callback's `context` as `Context | None`, so the poll's check is not read and every read of `context` is reported."
# ///
"""Blender calls an operator's `execute` or `invoke`, and a panel's `draw`, only right after its `poll()` returned
`True`, with the same context. So a pointer the poll checked is set in those callbacks. The checker reads what the
poll checks, narrows the pointer there and reports the read as an Implied narrowing; a pointer the poll did not
check stays an error."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import Object, Operator


class Rename(Operator):
    bl_idname = "context.rename_object"
    bl_label = "Rename"

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):
        assert_type(context.object, Object)  # ty: ignore[blender-narrowed-by-poll]
        context.object.name = "Renamed"  # ty: ignore[blender-narrowed-by-poll]
        context.active_bone.name = "Renamed"  # ty: ignore[invalid-assignment]
        return {"FINISHED"}
