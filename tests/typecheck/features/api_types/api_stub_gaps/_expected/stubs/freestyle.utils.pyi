"""Reference stub delta: BoundingBox documents its attributes, and the generators say what they yield."""

from collections.abc import Iterable, Iterator
from typing import Any

from freestyle.types import Stroke, StrokeVertex
from mathutils import Vector

class BoundingBox:
    minimum: Vector
    maximum: Vector
    size: int
    corners: tuple[Vector, Vector]

def get_strokes() -> tuple[Stroke, ...]: ...
def pairwise(iterable: Iterable[Any], types: tuple[type, ...] | None = None) -> Iterator[tuple[Any, Any]]: ...
def iter_t2d_along_stroke(stroke: Stroke) -> Iterator[float]: ...
def iter_distance_from_camera(stroke: Stroke, range_min: float, range_max: float, normfac: float) -> Iterator[tuple[StrokeVertex, float]]: ...
def stroke_normal(stroke: Stroke) -> Iterator[Vector]: ...
