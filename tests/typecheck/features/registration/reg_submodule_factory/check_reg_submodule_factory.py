"""Submodules listed in register_submodule_factory register their classes."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def registered() -> None:
    assert_type(bpy.ops.reg_submodule_factory.module(), Result)
    assert_type(bpy.ops.reg_submodule_factory.package(), Result)


def not_registered() -> None:
    bpy.ops.reg_submodule_factory.unlisted  # ty: ignore[unresolved-attribute]  # bare-ok: must stay missing: ty-blender must not add it
    bpy.ops.reg_submodule_factory.unlisted_module  # ty: ignore[unresolved-attribute]  # bare-ok: must stay missing: ty-blender must not add it
