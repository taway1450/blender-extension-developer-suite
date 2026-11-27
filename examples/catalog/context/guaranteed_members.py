# /// catalog
# title = "`context.scene` and its siblings in a callback"
# section = "members"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["context_members", "assumptions"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's stubs type the callback's `context` as `Context | None`, so every read of it is reported and `scene` keeps `None`."
# "fake-bpy-module/5.2" = "These stubs type the callback's `context` as `Context | None`, so every read of it is reported and `scene` keeps `None`."
# ///
"""The stubs type every context member `X | None`, since some context has none of them. But whenever Blender calls a
callback, `scene`, `view_layer`, `tool_settings`, `preferences`, `window_manager` and `blend_data` are set: they are
Guaranteed context members. The checker drops `None` from them inside the callback; in a helper function it reports
the read as an Assumption."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import Context, Operator, Scene, ViewLayer


class Report(Operator):
    bl_idname = "context.report_scene"
    bl_label = "Report"

    def execute(self, context):
        assert_type(context.scene, Scene)
        assert_type(context.view_layer, ViewLayer)
        return {"FINISHED"}


def frame(context: Context) -> int:
    return context.scene.frame_current  # ty: ignore[blender-assumed-context-member]
