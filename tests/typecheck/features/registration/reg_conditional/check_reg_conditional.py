"""Conditionally registered classes are in bpy.ops (not optional: they may be registered), and each use is reported as
an Assumption; the try block's body always runs, so its class is registered unconditionally."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def registered() -> None:
    assert_type(bpy.ops.reg_conditional.version(), Result)  # ty: ignore[blender-assumed-registration]
    assert_type(bpy.ops.reg_conditional.module_version(), Result)  # ty: ignore[blender-assumed-registration]
    assert_type(bpy.ops.reg_conditional.try_block(), Result)
    assert_type(bpy.ops.reg_conditional.hasattr(), Result)  # ty: ignore[blender-assumed-registration]
    assert_type(bpy.ops.reg_conditional.environment(), Result)  # ty: ignore[blender-assumed-registration]
