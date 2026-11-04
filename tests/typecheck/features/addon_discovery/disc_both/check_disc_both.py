"""With a manifest the add-on is an extension, whatever bl_info says: __package__ is bl_ext.<repository>.<id>."""

from __future__ import annotations

from typing import assert_type

from bpy.types import Scene


def package() -> None:
    assert_type(__package__, str)  # oracle-skip: stock ty types __package__ as str | None


def registered(scene: Scene) -> None:
    assert_type(scene.disc_both_marker, str)
