"""A math property takes any sequence of floats (a Matrix one of rows), and an array property any sequence of its
element type, also through a slice; reading them still gives the math object or the bpy_prop_array, and an element of
the wrong type is still reported. These are stub facts."""

from __future__ import annotations

from collections.abc import Sequence
from typing import assert_type

from bpy.types import Image, Light, Material, Object, bpy_prop_array
from mathutils import Color, Euler, Matrix, Quaternion, Vector


def as_floats(values: Sequence[float]) -> Sequence[float]:
    return values


def math(ob: Object, light: Light, rows: list[list[float]]) -> None:
    ob.location = (1, 1, 1)
    ob.rotation_euler = (0.0, 0.0, 1.0)
    ob.rotation_quaternion = [1.0, 0.0, 0.0, 0.0]
    ob.scale = Vector((2.0, 2.0, 2.0))
    ob.matrix_world = rows
    light.color = (1.0, 0.5, 0.0)
    assert_type(ob.location, Vector)  # bare-ok: a stub fact: reading still gives a Vector
    assert_type(ob.rotation_euler, Euler)  # bare-ok: a stub fact: reading still gives an Euler
    assert_type(ob.rotation_quaternion, Quaternion)  # bare-ok: a stub fact: reading still gives a Quaternion
    assert_type(ob.matrix_world, Matrix)  # bare-ok: a stub fact: reading still gives a Matrix
    assert_type(light.color, Color)  # bare-ok: a stub fact: reading still gives a Color
    ob.location = ("1", 1, 1)  # ty: ignore[invalid-assignment]  # bare-ok: a stub fact: a wrong element type is still reported
    ob.matrix_world = (1.0, 0.0, 0.0, 0.0)  # ty: ignore[invalid-assignment]  # bare-ok: a stub fact: a matrix takes rows


def arrays(ob: Object, image: Image, material: Material) -> None:
    ob.lock_location = (True, False, True)
    material.diffuse_color = (1.0, 0.0, 0.0, 1.0)
    image.pixels[:] = [0.5] * 16
    ob.color[0:3] = (0.25, 0.5, 0.75)
    ob.color[3] = 1.0
    assert_type(ob.lock_location, bpy_prop_array[bool])  # bare-ok: a stub fact: reading still gives a bpy_prop_array
    assert_type(image.pixels, bpy_prop_array[float])  # bare-ok: a stub fact: reading still gives a bpy_prop_array
    assert_type(as_floats(material.diffuse_color), Sequence[float])  # bare-ok: a stub fact: an array is a Sequence
    image.pixels = ["0.5"]  # ty: ignore[invalid-assignment]  # bare-ok: a stub fact: a wrong element type is still reported
    ob.color[0:2] = ("a", "b")  # ty: ignore[invalid-assignment]  # bare-ok: a stub fact: so is one assigned to a slice
