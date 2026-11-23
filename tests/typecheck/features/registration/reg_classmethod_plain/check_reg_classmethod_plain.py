"""A PropertyGroup's register() that is no classmethod is not run: the property it assigns does not exist."""

from __future__ import annotations

from bpy.types import Scene


def not_run(scene: Scene) -> None:
    scene.reg_classmethod_plain  # ty: ignore[missing-attribute]  # bare-ok: must stay missing: ty-blender must not add it
