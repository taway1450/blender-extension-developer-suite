"""The inverted reload guard: the `else` branch runs only on a reload."""

if "helpers" not in locals():
    from . import helpers
else:
    import importlib

    helpers = importlib.reload(helpers)

import bpy
from bpy.types import Operator

LABEL = "Run"


class REG_RELOAD_OT_run(Operator):
    bl_idname = "reg_reload.run"
    bl_label = helpers.LABEL

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(REG_RELOAD_OT_run)


def unregister():
    bpy.utils.unregister_class(REG_RELOAD_OT_run)
