"""Classes passed to register_classes_factory are registered when register() calls the result, and Blender adds
each to bpy.types: an operator under its idname's CATEGORY_OT_name form, whatever its class is called."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy
from bpy.types import Context, Scene

from . import REG_FACTORY_OT_first, SecondOperator

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def registered(scene: Scene) -> None:
    assert_type(bpy.ops.reg_factory.first(), Result)
    assert_type(bpy.ops.reg_factory.second(), Result)
    assert_type(bpy.ops.reg_factory.tools(), Result)
    assert_type(scene.reg_factory_label, str)


def in_bpy_types(context: Context) -> None:
    assert_type(bpy.types.REG_FACTORY_OT_first.poll(context), bool)
    assert_type(bpy.types.REG_FACTORY_OT_first().bl_idname, str)
    assert_type(bpy.types.REG_FACTORY_OT_first(), REG_FACTORY_OT_first)
    assert_type(bpy.types.REG_FACTORY_OT_second(), SecondOperator)
