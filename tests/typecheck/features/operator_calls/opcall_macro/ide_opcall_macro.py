"""What the editor shows for macro calls (check:ide; never imported).

The code under a ^completion marker is unfinished, as the user types it; check:features does not check ide_*.py
files, so the errors it causes do not count.
"""

from __future__ import annotations

import bpy


def signature() -> None:
    bpy.ops.opcall_macro.combo()
    #                          ^signature
