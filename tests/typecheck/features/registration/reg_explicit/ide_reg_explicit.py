"""What the editor shows for registered operators (check:ide; never imported).

The code under a ^completion marker is unfinished, as the user types it; check:features does not check ide_*.py
files, so the errors it causes do not count.
"""

from __future__ import annotations

import bpy


def completion() -> None:
    bpy.ops.reg_exp
    #              ^completion reg_explicit
    bpy.ops.reg_explicit.
    #                    ^completion dotted imported alias


def hover() -> None:
    bpy.ops.reg_explicit.dotted
    #                    ^hover
    #                    ^hover-contains "count"
