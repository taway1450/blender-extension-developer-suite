"""An extension's package is bl_ext.<repository>.<id>: always a str, the repository is only known when installed."""

from __future__ import annotations

from typing import assert_type

from bpy.types import Scene


def package() -> None:
    assert_type(__package__, str)  # oracle-skip: stock ty types __package__ as str | None


def registered(scene: Scene) -> None:
    assert_type(scene.disc_extension_marker, int)  # the register() of this addon is found
