"""Classes registered by unreachable code are not in bpy.ops."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def registered() -> None:
    assert_type(bpy.ops.regchk_unreachable.used(), Result)
    assert_type(bpy.ops.regchk_unreachable.late(), Result)  # registered by a timer register() starts


def not_registered() -> None:
    bpy.ops.regchk_unreachable.extra  # ty: ignore[unresolved-attribute]  # bare-ok: must stay missing: ty-blender must not add it
    bpy.ops.regchk_unreachable.lost  # ty: ignore[unresolved-attribute]  # bare-ok: must stay missing: ty-blender must not add it
