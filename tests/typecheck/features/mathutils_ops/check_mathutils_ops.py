"""Expected types of mathutils operators, swizzles and conversions."""

from __future__ import annotations

from typing import assert_type

from bpy.types import Object
from mathutils import Euler, Matrix, Quaternion, Vector


def vector_ops(a: Vector, b: Vector) -> None:
    assert_type(a + b, Vector)
    assert_type(a - b, Vector)
    assert_type(a * 2.0, Vector)
    assert_type(2.0 * a, Vector)
    assert_type(a / 2, Vector)
    assert_type(-a, Vector)
    assert_type(a @ b, float)  # dot product
    assert_type(a.dot(b), float)
    assert_type(a.cross(b), Vector | float)  # a float for 2D vectors
    assert_type(a.length, float)
    assert_type(a.normalized(), Vector)
    assert_type(a.x, float)
    assert_type(a.xy, Vector)  # swizzle
    assert_type(a[0], float)
    assert_type(a.to_tuple(), tuple[float, ...])
    a + 1  # ty: ignore[unsupported-operator]


def matrix_ops(m: Matrix, v: Vector, q: Quaternion) -> None:
    assert_type(m @ m, Matrix)
    assert_type(m @ v, Vector)
    assert_type(q @ v, Vector)
    assert_type(m.inverted(), Matrix)
    assert_type(m.to_translation(), Vector)
    assert_type(m.to_euler(), Euler)
    assert_type(m.to_quaternion(), Quaternion)
    assert_type(Matrix.Translation((1.0, 2.0, 3.0)), Matrix)
    assert_type(Matrix.Identity(4), Matrix)


def object_transforms(obj: Object) -> None:
    assert_type(obj.location, Vector)
    assert_type(obj.rotation_euler, Euler)
    assert_type(obj.matrix_world, Matrix)
    assert_type(obj.matrix_world @ obj.location, Vector)
    obj.location = (0.0, 0.0, 1.0)
    obj.location = obj.location + Vector((0.0, 0.0, 1.0))
