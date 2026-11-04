"""Classes registered through imported modules are in bpy.ops."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy
from bpy.types import Scene

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def registered() -> None:
    assert_type(bpy.ops.reg_imports.reloaded(), Result)
    assert_type(bpy.ops.reg_imports.renamed(), Result)
    assert_type(bpy.ops.reg_imports.star(), Result)
    assert_type(bpy.ops.reg_imports.class_import(), Result)
    assert_type(bpy.ops.reg_imports.nested(), Result)
    assert_type(bpy.ops.reg_imports.lazy(), Result)
