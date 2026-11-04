"""Feature test: operator classes written the way the Blender templates write them
(scripts/templates_py/operator_simple.py, operator_modal.py)."""

from __future__ import annotations

import bpy
from bpy.types import Context, Event, Operator


class OPERATOR_BASICS_OT_simple(Operator):
    """Tooltip of the simple operator"""

    bl_idname = "operator_basics.simple"
    bl_label = "Simple"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: Context) -> bool:
        return context.active_object is not None

    def execute(self, context: Context) -> set[str]:
        self.report({"INFO"}, "Executed")
        return {"FINISHED"}


class OPERATOR_BASICS_OT_modal(Operator):
    bl_idname = "operator_basics.modal"
    bl_label = "Modal"

    def invoke(self, context: Context, event: Event) -> set[str]:
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context: Context, event: Event) -> set[str]:
        if event.type in {"RIGHTMOUSE", "ESC"}:
            return {"CANCELLED"}
        if event.type == "LEFTMOUSE" and event.value == "RELEASE":
            return {"FINISHED"}
        return {"PASS_THROUGH"}


class OPERATOR_BASICS_OT_untyped(Operator):
    """Operator without annotations, as most addons write them"""

    bl_idname = "operator_basics.untyped"
    bl_label = "Untyped"

    def execute(self, context):
        return {"FINISHED"}


classes = (OPERATOR_BASICS_OT_simple, OPERATOR_BASICS_OT_modal, OPERATOR_BASICS_OT_untyped)


def register() -> None:
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
