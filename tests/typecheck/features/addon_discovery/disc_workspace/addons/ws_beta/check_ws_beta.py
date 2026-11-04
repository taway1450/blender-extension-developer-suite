"""ws_beta registers Scene.ws_value as a str; what ws_alpha registers does not exist here."""

from __future__ import annotations

from typing import assert_type

from bpy.types import Scene


def registered(scene: Scene) -> None:
    assert_type(scene.ws_value, str)  # oracle-skip: two extensions in one folder share one _expected/
    scene.ws_alpha_only  # ty: ignore[unresolved-attribute]
