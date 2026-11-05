"""The addon sees its own registrations only."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy
from bpy.types import Scene

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def own(scene: Scene) -> None:
    assert_type(bpy.ops.regchk_isolation_b.run(), Result)
    assert_type(scene.regchk_isolation_b_value, int)


def other_addons(scene: Scene) -> None:
    bpy.ops.regchk_isolation_a  # ty: ignore[unresolved-attribute]  # bare-ok: must stay missing: ty-blender must not add it
    scene.regchk_isolation_a_value  # ty: ignore[unresolved-attribute]  # bare-ok: must stay missing: ty-blender must not add it
    bpy.ops.regchk_shared  # ty: ignore[unresolved-attribute]  # bare-ok: must stay missing: ty-blender must not add it
