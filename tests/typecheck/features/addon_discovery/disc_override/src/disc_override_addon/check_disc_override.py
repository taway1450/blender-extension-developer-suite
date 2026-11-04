"""An add-on found through [tool.blender] in pyproject.toml is treated like an extension."""

from __future__ import annotations

from typing import assert_type

from bpy.types import Scene


def package() -> None:
    assert_type(__package__, str)  # oracle-skip: stock ty types __package__ as str | None


def registered(scene: Scene) -> None:
    assert_type(scene.disc_override_marker, float)
