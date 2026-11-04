"""Everything register() reaches through calls counts as registered."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy
from bpy.types import Scene

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def registered(scene: Scene) -> None:
    assert_type(bpy.ops.reg_delegation.helper(), Result)
    assert_type(bpy.ops.reg_delegation.nested(), Result)
    assert_type(bpy.ops.reg_delegation.module_call(), Result)
    assert_type(bpy.ops.reg_delegation.module_loop_a(), Result)
    assert_type(bpy.ops.reg_delegation.module_loop_b(), Result)
    assert_type(bpy.ops.reg_delegation.function_loop(), Result)
    assert_type(bpy.ops.reg_delegation.static_method(), Result)
    assert_type(scene.reg_delegation_factor, float)
