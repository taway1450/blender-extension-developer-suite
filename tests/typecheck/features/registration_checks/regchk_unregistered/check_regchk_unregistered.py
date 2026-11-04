"""Only registered operators are in bpy.ops."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def registered() -> None:
    assert_type(bpy.ops.regchk_unregistered.used(), Result)
    bpy.ops.regchk_unregistered.used(steps=3)


def not_registered() -> None:
    bpy.ops.regchk_unregistered.forgotten  # ty: ignore[unresolved-attribute]
    bpy.ops.regchk_unregistered.imported  # ty: ignore[unresolved-attribute]
    bpy.ops.regchk_unregistered.orphan  # ty: ignore[unresolved-attribute]
