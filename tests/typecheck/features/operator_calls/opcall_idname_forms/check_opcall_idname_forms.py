"""Operators are found by their evaluated bl_idname."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def evaluated() -> None:
    assert_type(bpy.ops.opcall_idname_forms.constant(), Result)
    assert_type(bpy.ops.opcall_idname_forms.concat(), Result)
    assert_type(bpy.ops.opcall_idname_forms.fstring(), Result)
    assert_type(bpy.ops.opcall_idname_forms.fstring_copy(), Result)
    assert_type(bpy.ops.opcall_idname_forms.from_mixin(), Result)


def runtime_only() -> None:
    bpy.ops.opcall_idname_forms.runtime  # ty: ignore[unresolved-attribute]  # bare-ok: must stay missing: ty-blender must not add it
