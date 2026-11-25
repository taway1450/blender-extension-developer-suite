"""The measurement drawn over the 3D viewport: the picked points, the line between them and its length."""

import blf
import bpy
import gpu
from bpy.types import SpaceView3D
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

points: list[Vector] = []
_handle = None


def draw_overlay():
    # Blender calls a draw handler while it draws a region of the editor it was added to.
    # demo: blender-assumed-editor-member
    region = bpy.context.region
    region_3d = bpy.context.space_data.region_3d
    on_screen = [
        view3d_utils.location_3d_to_region_2d(region, region_3d, point)
        for point in points
    ]
    coords = [co for co in on_screen if co is not None]
    if not coords:
        return

    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    primitive = "LINE_STRIP" if len(coords) > 1 else "POINTS"
    batch = batch_for_shader(shader, primitive, {"pos": coords})
    gpu.state.blend_set("ALPHA")
    gpu.state.line_width_set(2.0)
    gpu.state.point_size_set(6.0)
    shader.uniform_float("color", (1.0, 0.6, 0.1, 1.0))
    batch.draw(shader)
    gpu.state.blend_set("NONE")

    if len(points) == 2 and len(coords) == 2:
        middle = (coords[0] + coords[1]) / 2
        blf.position(0, middle.x + 8, middle.y + 8, 0)
        blf.size(0, 14.0)
        blf.draw(0, f"{(points[1] - points[0]).length:.3f}")


def add_handler():
    global _handle
    if _handle is None:
        _handle = SpaceView3D.draw_handler_add(draw_overlay, (), "WINDOW", "POST_PIXEL")


def remove_handler():
    global _handle
    if _handle is not None:
        SpaceView3D.draw_handler_remove(_handle, "WINDOW")
        _handle = None
