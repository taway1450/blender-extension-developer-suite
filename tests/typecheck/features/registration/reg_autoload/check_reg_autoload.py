"""With registration the checker cannot follow, every Blender class of the addon counts as registered."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy
from bpy.types import Scene

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def registered() -> None:
    assert_type(bpy.ops.reg_autoload.first(), Result)
    assert_type(bpy.ops.reg_autoload.second(), Result)
    assert_type(bpy.ops.reg_autoload.panel_helper(), Result)
