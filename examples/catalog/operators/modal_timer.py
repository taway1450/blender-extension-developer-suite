# /// catalog
# title = "Timers and `modal_handler_add`"
# section = "modal"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["context_members"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's stubs type the callback's `context` as `Context | None`, so `window_manager` keeps `None` and every read of `context` and `event` is reported."
# "fake-bpy-module/5.2" = "These stubs type the callback's `context` as `Context | None`, so `window_manager` keeps `None` and every read of `context` and `event` is reported."
# ///
"""`context.window_manager`, which a modal operator needs for `modal_handler_add` and its timers, is always set, so
the checker drops the stubs' `None` from it. The operator adds itself as a handler in `invoke` and returns
`{"RUNNING_MODAL"}`; Blender then calls `modal` for every event, a timer's `TIMER` events among them, until it returns
`{"FINISHED"}` or `{"CANCELLED"}`."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import Operator, Timer, WindowManager


class Watch(Operator):
    bl_idname = "operators.watch"
    bl_label = "Watch"

    timer: Timer | None = None

    def invoke(self, context, event):
        assert_type(context.window_manager, WindowManager)
        self.timer = context.window_manager.event_timer_add(0.5, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "TIMER":
            print("tick")
        if event.type == "ESC":
            if self.timer is not None:
                context.window_manager.event_timer_remove(self.timer)
            return {"CANCELLED"}
        return {"PASS_THROUGH"}
