"""Feature test: mathutils arithmetic as addons use it."""

from __future__ import annotations

from mathutils import Matrix, Vector


def midpoint(a: Vector, b: Vector) -> Vector:
    return (a + b) / 2


def transformed(matrix: Matrix, point: Vector) -> Vector:
    return matrix @ point


def register() -> None:
    pass


def unregister() -> None:
    pass
