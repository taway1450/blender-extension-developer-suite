"""Properties assigned in the register() classmethod of a registered PropertyGroup are Registered properties;
those of a group nobody registers are not."""

from __future__ import annotations

from typing import assert_type

from bpy.types import Object, Scene

from . import REG_CLASSMETHOD_PG_object, REG_CLASSMETHOD_PG_scene


def registered(scene: Scene, obj: Object) -> None:
    assert_type(scene.reg_classmethod, REG_CLASSMETHOD_PG_scene)
    assert_type(scene.reg_classmethod.count, int)
    assert_type(obj.reg_classmethod, REG_CLASSMETHOD_PG_object)
    assert_type(obj.reg_classmethod.weight, int)


def not_registered(scene: Scene) -> None:
    scene.reg_classmethod_never  # ty: ignore[unresolved-attribute]  # bare-ok: must stay missing: ty-blender must not add it
