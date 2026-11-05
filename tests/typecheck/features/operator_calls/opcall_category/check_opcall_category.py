"""Addon operators in Blender's categories and in a shared new category."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def builtin_category() -> None:
    assert_type(bpy.ops.object.opcall_category_scale(factor=2.0), Result)
    assert_type(bpy.ops.object.opcall_category_scale.idname(), Literal["OBJECT_OT_opcall_category_scale"])
    bpy.ops.object.opcall_category_scale(factor="2")  # ty: ignore[invalid-argument-type]
    bpy.ops.object.select_all(action="SELECT")  # the built-in operators stay
    bpy.ops.object.opcall_category_missing  # ty: ignore[unresolved-attribute]  # bare-ok: must stay missing: ty-blender must not add it


def shared_category() -> None:
    assert_type(bpy.ops.opcall_category.first(), Result)
    assert_type(bpy.ops.opcall_category.second(), Result)
