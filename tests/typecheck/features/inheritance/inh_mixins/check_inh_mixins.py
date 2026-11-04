"""Mixin annotations are properties in either order."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy
from bpy.types import Scene

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def operators() -> None:
    assert_type(bpy.ops.inh_mixins.first(count=1, label="x"), Result)
    assert_type(bpy.ops.inh_mixins.last(count=1, label="x"), Result)
    assert_type(bpy.ops.inh_mixins.based(count=1), Result)
    bpy.ops.inh_mixins.based(label="x")  # ty: ignore[unknown-argument]
    assert_type(bpy.ops.inh_mixins.poll_last(), Result)
    assert_type(bpy.ops.inh_mixins.keywords_first(), Result)
    assert_type(bpy.ops.inh_mixins.keywords_last(), Result)
