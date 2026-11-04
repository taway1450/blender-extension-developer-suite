"""Classes passed to register_classes_factory are registered when register() calls the result."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy
from bpy.types import Scene

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def registered(scene: Scene) -> None:
    assert_type(bpy.ops.reg_factory.first(), Result)
    assert_type(bpy.ops.reg_factory.second(), Result)
    assert_type(bpy.ops.reg_factory.tools(), Result)
    assert_type(scene.reg_factory_label, str)
