"""Classes registered in loops over sequences are in bpy.ops."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def registered() -> None:
    assert_type(bpy.ops.reg_loop.tuple(), Result)
    assert_type(bpy.ops.reg_loop.list(), Result)
    assert_type(bpy.ops.reg_loop.appended(), Result)
    assert_type(bpy.ops.reg_loop.extended(), Result)
    assert_type(bpy.ops.reg_loop.concat(), Result)
    assert_type(bpy.ops.reg_loop.unpacked(), Result)
    assert_type(bpy.ops.reg_loop.nested_a(), Result)
    assert_type(bpy.ops.reg_loop.nested_b(), Result)
