"""A legacy add-on is imported under its own name, so __package__ is known exactly."""

from __future__ import annotations

from typing import Literal, assert_type

from bpy.types import Scene


def package() -> None:
    assert_type(__package__, Literal["disc_legacy"])  # oracle-skip: stock ty types __package__ as str | None


def registered(scene: Scene) -> None:
    assert_type(scene.disc_legacy_marker, int)
