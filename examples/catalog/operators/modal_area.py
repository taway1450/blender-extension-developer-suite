# /// catalog
# title = "`context.area` in `modal`"
# section = "modal"
# status = "not-handled"
# features = ["context_members"]
# later = "editor-members-in-modal"
#
# [future]
# class = "planned"
# note = "Narrow `area`, `region` and `space_data` in `modal` of an operator started from an editor."
# tracked = "later/editor-members-in-modal"
#
# [differs]
# "builtin/5.2" = "Blender 5.2's stubs type the callback's `context` as `Context | None`, so the read of `context` is reported as well as the one of `area`."
# "fake-bpy-module/5.2" = "These stubs type the callback's `context` as `Context | None`, so the read of `context` is reported as well as the one of `area`."
# ///
"""A modal operator started from an editor gets its later events in `modal`, with that editor's area. The stubs type
`context.area` as `Area | None`, and the checker does not narrow it there yet, so a redraw of the area is reported."""

from bpy.types import Operator


class Drag(Operator):
    bl_idname = "operators.drag"
    bl_label = "Drag"

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        # gap: the editor's area is not known in modal
        context.area.tag_redraw()
        if event.type in {"LEFTMOUSE", "ESC"}:
            return {"FINISHED"}
        return {"RUNNING_MODAL"}
