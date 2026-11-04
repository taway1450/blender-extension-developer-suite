"""The re-exported register() is the entry point."""

from __future__ import annotations

from typing import assert_type

from bpy.types import Scene


def registered(scene: Scene) -> None:
    assert_type(scene.disc_register_reexport_marker, bool)
