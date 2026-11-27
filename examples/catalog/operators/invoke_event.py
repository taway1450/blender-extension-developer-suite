# /// catalog
# title = "`invoke` with an event"
# section = "callbacks"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["inheritance"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's stubs type `invoke`'s `event` as `Event | None`, so its reads are reported."
# "fake-bpy-module/5.2" = "These stubs type `invoke`'s `event` as `Event | None`, so its reads are reported."
# ///
"""An unannotated `invoke` gets its `event` typed as an `Event`, from `Operator.invoke`. Blender calls `invoke` when the
operator is started from the UI, with the event that started it: a key or a mouse click, and where the mouse was."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import Event, Operator


class Place(Operator):
    bl_idname = "operators.place"
    bl_label = "Place"

    def invoke(self, context, event):
        assert_type(event, Event)
        print(event.mouse_region_x, event.mouse_region_y)
        return self.execute(context)

    def execute(self, context):
        return {"FINISHED"}
