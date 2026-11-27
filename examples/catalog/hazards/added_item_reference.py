# /// catalog
# title = "A collection item after `add()`"
# section = "stale-data"
# status = "not-handled"
# blender-docs = ["info_gotchas_crashes"]
#
# [future]
# class = "not-checkable"
# note = "Which calls re-allocate a collection's array is decided in Blender's C code while it runs."
# ///
"""Adding points to a curve, or vertices, edges and faces to a mesh, re-allocates the array that holds them, so an
item read before the `add()` points to freed memory and can crash Blender. Read the item again after adding."""

from bpy.types import Curve


def add_point(curve: Curve) -> None:
    points = curve.splines[0].bezier_points
    first = points[0]
    points.add(1)  # re-allocates the points: `first` is stale now
    first = points[0]
    first.co.x = 0.0
