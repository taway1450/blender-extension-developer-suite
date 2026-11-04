"""mathutils values are accepted as defaults; the values have the mathutils types, however imported."""

from __future__ import annotations

from typing import assert_type

import mathutils
from bpy.types import Scene
from mathutils import Euler, Matrix, Quaternion

from . import SYM_MATHUTILS_Settings


def values(s: SYM_MATHUTILS_Settings) -> None:
    assert_type(s.location, mathutils.Vector)
    assert_type(s.tint, mathutils.Color)
    assert_type(s.rotation, Euler)
    assert_type(s.orientation, Quaternion)
    assert_type(s.transform, Matrix)
    assert_type(s.transform @ s.location, mathutils.Vector)
    s.location = mathutils.Vector((1.0, 2.0, 3.0))
    s.rotation = Euler((0.0, 0.0, 0.0))


def registered(scene: Scene) -> None:
    assert_type(scene.sym_mathutils.location.z, float)
