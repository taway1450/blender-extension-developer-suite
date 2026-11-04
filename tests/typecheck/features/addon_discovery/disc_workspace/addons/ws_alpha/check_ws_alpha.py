"""ws_alpha is an extension of its own: its Scene.ws_value is an int."""

from __future__ import annotations

from typing import assert_type

from bpy.types import Scene


def registered(scene: Scene) -> None:
    assert_type(scene.ws_value, int)  # oracle-skip: two extensions in one folder share one _expected/
    assert_type(scene.ws_alpha_only, int)  # oracle-skip: two extensions in one folder share one _expected/
