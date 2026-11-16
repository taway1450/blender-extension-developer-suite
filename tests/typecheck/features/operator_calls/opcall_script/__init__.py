"""Not an add-on (no manifest, no bl_info): a script like those in Blender's ``scripts/startup``, which calls built-in
operators with the positional execution context and undo flag as any add-on does."""

import bpy


def open_add_menu() -> None:
    bpy.ops.wm.call_menu("INVOKE_DEFAULT", name="VIEW3D_MT_add")
