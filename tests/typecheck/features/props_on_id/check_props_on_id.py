"""Expected types of properties that register() adds to existing Blender types.

These attributes only exist at runtime, after register(). The assertions state what an addon author
expects to read back; whether a type checker can know this is an open question (see the research note).
"""

from __future__ import annotations

from typing import assert_type

from bpy.types import Object, Scene

from . import PROPS_ON_ID_Settings


def read_back(scene: Scene, obj: Object) -> None:
    assert_type(scene.props_on_id, PROPS_ON_ID_Settings)
    assert_type(scene.props_on_id.count, int)
    assert_type(obj.props_on_id_weight, float)


def unknown_attribute(scene: Scene) -> None:
    # Attributes that nobody registered are still errors.
    scene.props_on_id_missing  # ty: ignore[unresolved-attribute]
