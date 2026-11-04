"""Feature test: reading bpy.context members inside an operator."""

from __future__ import annotations

import bpy
from bpy.types import Context, Operator


class CONTEXT_MEMBERS_OT_report_selection(Operator):
    bl_idname = "context_members.report_selection"
    bl_label = "Report Selection"

    def execute(self, context: Context) -> set[str]:
        names = [obj.name for obj in context.selected_objects]
        active = context.active_object
        if active is not None:
            names.append(f"active: {active.name}")
        self.report({"INFO"}, ", ".join(names) or context.scene.name)
        return {"FINISHED"}


def register() -> None:
    bpy.utils.register_class(CONTEXT_MEMBERS_OT_report_selection)


def unregister() -> None:
    bpy.utils.unregister_class(CONTEXT_MEMBERS_OT_report_selection)
