"""What the editor shows for a built-in operator call (check:ide; never imported)."""

from __future__ import annotations

import bpy


def hover() -> None:
    bpy.ops.wm.call_menu("INVOKE_DEFAULT", name="VIEW3D_MT_add")
    #          ^hover
    #          ^hover-contains "bpy.ops.wm.call_menu(execution_context, undo, *, name: str)"


def signature() -> None:
    bpy.ops.object.select_all("EXEC_DEFAULT", True, action="SELECT")
    #                                               ^signature
