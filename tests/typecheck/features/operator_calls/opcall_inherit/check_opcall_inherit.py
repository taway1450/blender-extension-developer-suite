"""Inherited and mixin properties are keyword arguments; redeclared ones take the subclass type."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def derived() -> None:
    assert_type(bpy.ops.opcall_inherit.derived(count=1, size=2.0, mode="text", label="x"), Result)
    bpy.ops.opcall_inherit.derived(mode=1)  # ty: ignore[invalid-argument-type]


def base() -> None:
    assert_type(bpy.ops.opcall_inherit.base(size=1.0, mode=1), Result)
    bpy.ops.opcall_inherit.base(mode="text")  # ty: ignore[invalid-argument-type]
    bpy.ops.opcall_inherit.base(count=1)  # ty: ignore[unknown-argument]
