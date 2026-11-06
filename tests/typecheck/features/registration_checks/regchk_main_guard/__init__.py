"""Feature test: the shape of Blender's bundled add-ons. A reload guard re-imports the add-on's module, register()
registers each class once in a loop, and the file ends with `if __name__ == "__main__": register()` for running it
from the text editor. Blender imports an add-on as a module, so that block never runs and nothing is registered
twice: no rule reports anything."""

if "bpy" in locals():
    import importlib

    if "ops" in locals():
        importlib.reload(ops)

import bpy
from bpy.types import Panel

from . import ops


class REGCHK_MAIN_GUARD_PT_panel(Panel):
    bl_label = "Run"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        self.layout.operator(ops.REGCHK_MAIN_GUARD_OT_run.bl_idname)


classes = (
    ops.REGCHK_MAIN_GUARD_OT_run,
    REGCHK_MAIN_GUARD_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
