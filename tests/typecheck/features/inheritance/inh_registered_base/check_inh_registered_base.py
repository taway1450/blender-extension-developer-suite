"""The operators exist and keep their properties; only their runtime behaviour is broken."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy
from bpy.types import Scene

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def operators() -> None:
    assert_type(bpy.ops.inh_registered_base.parent(count=1), Result)
    assert_type(bpy.ops.inh_registered_base.child(count=1), Result)
    assert_type(bpy.ops.inh_registered_base.late_parent(), Result)
    assert_type(bpy.ops.inh_registered_base.early_child(), Result)
