"""Conditionally registered classes are in bpy.ops (not optional: they may be registered)."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy
from bpy.types import Scene

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def registered() -> None:
    assert_type(bpy.ops.reg_conditional.version(), Result)
    assert_type(bpy.ops.reg_conditional.module_version(), Result)
    assert_type(bpy.ops.reg_conditional.try_block(), Result)
    assert_type(bpy.ops.reg_conditional.hasattr(), Result)
    assert_type(bpy.ops.reg_conditional.environment(), Result)
