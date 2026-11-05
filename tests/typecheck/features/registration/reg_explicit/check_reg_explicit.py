"""Every way of calling register_class registers the class; an operator nobody registers is not in bpy.ops."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy
from bpy.types import Scene

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def registered(scene: Scene) -> None:
    assert_type(bpy.ops.reg_explicit.dotted(), Result)
    assert_type(bpy.ops.reg_explicit.imported(), Result)
    assert_type(bpy.ops.reg_explicit.alias(), Result)
    bpy.ops.reg_explicit.dotted(count=2)
    bpy.ops.reg_explicit.dotted(count="2")  # ty: ignore[invalid-argument-type]
    assert_type(scene.reg_explicit_count, int)


def not_registered() -> None:
    bpy.ops.reg_explicit.never  # ty: ignore[unresolved-attribute]  # bare-ok: must stay missing: ty-blender must not add it
