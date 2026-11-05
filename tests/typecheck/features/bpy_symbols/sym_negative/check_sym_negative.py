"""Only calls of the real bpy.props functions declare properties."""

from __future__ import annotations

from typing import Any, assert_type

import bpy

from . import props
from .fakes import IntProperty, PropertyGroup


class LocalFunctions(bpy.types.PropertyGroup):
    count: IntProperty()  # ty: ignore[invalid-type-form]  # bare-ok: stock ty's error must stay on a class Blender does not register
    factor: props.FloatProperty()  # ty: ignore[invalid-type-form]  # bare-ok: stock ty's error must stay on a class Blender does not register


class OnFakeBase(PropertyGroup):
    # Not a bpy_struct, but it may be a mixin of one: annotations with real properties are accepted and typed.
    real: bpy.props.IntProperty()  # oracle-skip: stock ty rejects calls in annotations


def mixin_values(o: OnFakeBase) -> None:
    assert_type(o.real, int)  # oracle-skip: the class is in this file, so no reference stub can type it


def shadowed(bpy: Any) -> None:
    # A parameter called bpy is not the bpy module.
    class Local(bpy.types.PropertyGroup):
        value: bpy.props.IntProperty()  # ty: ignore[invalid-type-form]  # bare-ok: stock ty's error must stay on a class Blender does not register
