"""Registered classes have the properties of all their bases; the unregistered bases are no operators."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy
from bpy.types import Scene

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def operators() -> None:
    assert_type(bpy.ops.inh_chains.leaf(count=1, label="x", factor=0.5), Result)
    assert_type(bpy.ops.inh_chains.sibling(count=1), Result)
    bpy.ops.inh_chains.sibling(label="x")  # ty: ignore[no-matching-overload]
    bpy.ops.inh_chains.base  # ty: ignore[unresolved-attribute]  # bare-ok: must stay missing: ty-blender must not add it
    bpy.ops.inh_chains.middle  # ty: ignore[unresolved-attribute]  # bare-ok: must stay missing: ty-blender must not add it


def groups(scene: Scene) -> None:
    assert_type(scene.inh_chains_c.a, int)
    assert_type(scene.inh_chains_c.b, str)
    assert_type(scene.inh_chains_c.c, float)
