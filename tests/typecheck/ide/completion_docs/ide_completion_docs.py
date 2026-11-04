"""Completions and their documentation (check:ide; never imported).

The code under a ^completion marker is an unfinished name, as the user types it; check:features does not
check ide_*.py files, so the resulting unresolved-attribute errors don't count.
"""

from __future__ import annotations

import bpy
from bpy.types import Object


def attribute_completion(obj: Object) -> None:
    obj.locat
    #        ^completion location
    obj.select_s
    #           ^completion select_set


def operator_completion() -> None:
    bpy.ops.mesh.primitive_cube_a
    #                            ^completion primitive_cube_add
