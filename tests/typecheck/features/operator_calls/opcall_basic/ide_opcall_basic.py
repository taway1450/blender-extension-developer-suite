"""What the editor shows for operator calls (check:ide; never imported).

The code under a ^completion marker is unfinished, as the user types it; check:features does not check ide_*.py
files, so the errors it causes do not count.
"""

from __future__ import annotations

import bpy


def signature() -> None:
    bpy.ops.opcall_basic.all()
    #                        ^signature


def completion() -> None:
    bpy.ops.opcall_basic.al
    #                      ^completion all
    bpy.ops.opcall_basic.all(int_v)
    #                             ^completion int_value=
    bpy.ops.opcall_basic.dropped(e)
    #                             ^completion before=


def hover() -> None:
    bpy.ops.opcall_basic.all
    #                    ^hover
    bpy.ops.opcall_basic.all.idname()
    #                        ^hover-contains "OPCALL_BASIC_OT_all"
