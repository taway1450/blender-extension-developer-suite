"""The operators: scatter, reseed, clear, and a ground plane to scatter onto."""

from __future__ import annotations

import math
import random

import bpy
from bpy.props import BoolProperty, IntProperty
from bpy.types import Operator
from mathutils import Vector

from .preferences import get_preferences
from .properties import ScatterSettings


# demo: inheritance
class ActiveMeshMixin:
    """For operators that work on the active object: a mesh object, in Object Mode."""

    @classmethod
    def poll(cls, context):
        active = context.active_object
        return active is not None and active.type == "MESH" and context.mode == "OBJECT"


def offsets(settings: ScatterSettings, count: int, rng: random.Random) -> list[Vector]:
    """Where the copies go, relative to the source and before the surface is applied."""
    radius = settings.radius
    if settings.distribution == "GRID":
        side = math.ceil(math.sqrt(count))
        step = 2 * radius / max(side - 1, 1)
        grid = [
            Vector((x * step - radius, y * step - radius, 0.0))
            for y in range(side)
            for x in range(side)
        ]
        return grid[:count]
    points = []
    for index in range(count):
        if settings.distribution == "RING":
            angle, distance = math.tau * index / count, radius
        else:
            angle = rng.uniform(0.0, math.tau)
            distance = radius * math.sqrt(rng.random())
        points.append(
            Vector((math.cos(angle) * distance, math.sin(angle) * distance, 0.0))
        )
    return points


def remove_copies(settings: ScatterSettings) -> int:
    removed = 0
    for item in settings.placed:
        if item.instance is not None:
            bpy.data.objects.remove(item.instance)
            removed += 1
    settings.placed.clear()
    return removed


class OBJECT_OT_scatter_tools_scatter(ActiveMeshMixin, Operator):
    """Scatter linked copies of the active object around it"""

    bl_idname = "object.scatter_tools_scatter"
    bl_label = "Scatter"
    bl_options = {"REGISTER", "UNDO"}

    count: IntProperty(
        name="Count",
        description="Number of copies; 0 uses the scene's count",
        default=0,
        min=0,
        max=1000,
    )
    keep_previous: BoolProperty(
        name="Keep Previous",
        description="Keep the copies of earlier runs",
        default=False,
    )

    def invoke(self, context, event):
        if event.shift:
            self.count = get_preferences(context).default_count
        return self.execute(context)

    def execute(self, context):
        settings = context.scene.scatter_tools
        # demo: blender-narrowed-by-poll
        source = context.active_object
        mesh = source.data
        if not self.keep_previous:
            remove_copies(settings)

        rng = random.Random(settings.seed)
        collection = settings.target_collection or context.scene.collection
        surface = settings.surface
        low, high = settings.scale_range
        points = offsets(settings, self.count or settings.count, rng)
        for offset in points:
            # demo: bpy_symbols
            location = source.matrix_world @ (offset + settings.offset)
            if surface is not None:
                to_surface = surface.matrix_world.inverted()
                hit, nearest, _normal, _face = surface.closest_point_on_mesh(
                    to_surface @ location
                )
                if hit:
                    location = surface.matrix_world @ nearest

            copy = source.copy()
            copy.location = location
            if "ROTATION" in settings.randomize:
                copy.rotation_euler.z = rng.uniform(0.0, math.tau)
            if "SCALE" in settings.randomize:
                copy.scale = source.scale * rng.uniform(low, high)
            copy.color = (*settings.tint, 1.0)
            copy.is_scatter_copy = True
            collection.objects.link(copy)

            item = settings.placed.add()
            item.name = copy.name
            item.instance = copy

        settings.preview_dirty = False
        if get_preferences(context).show_stats:
            faces = len(mesh.polygons) * len(points)
            self.report(
                {"INFO"},
                f"Scattered {len(points)} copies of {source.name} ({faces} faces)",
            )
        return {"FINISHED"}


class OBJECT_OT_scatter_tools_reseed(ActiveMeshMixin, Operator):
    """Scatter again with the next seed"""

    bl_idname = "object.scatter_tools_reseed"
    bl_label = "Reseed"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        context.scene.scatter_tools.seed += 1
        # demo: operator_calls
        return bpy.ops.object.scatter_tools_scatter("EXEC_DEFAULT", keep_previous=False)


class OBJECT_OT_scatter_tools_clear(Operator):
    """Remove the copies of earlier runs"""

    bl_idname = "object.scatter_tools_clear"
    bl_label = "Clear Copies"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return len(context.scene.scatter_tools.placed) > 0

    def execute(self, context):
        removed = remove_copies(context.scene.scatter_tools)
        self.report({"INFO"}, f"Removed {removed} copies")
        return {"FINISHED"}


class OBJECT_OT_scatter_tools_ground(Operator):
    """Add a ground plane the size of the scatter and scatter onto it"""

    bl_idname = "object.scatter_tools_ground"
    bl_label = "Add Ground"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.scatter_tools
        size = settings.radius * 1.2
        corners = [
            (-size, -size, 0.0),
            (size, -size, 0.0),
            (size, size, 0.0),
            (-size, size, 0.0),
        ]
        mesh = bpy.data.meshes.new("Scatter Ground")
        mesh.from_pydata(corners, [], [(0, 1, 2, 3)])

        # demo: type_narrowing
        ground = bpy.data.objects.new("Scatter Ground", mesh)
        ground.data.materials.clear()
        subdivision = ground.modifiers.new("Subdivide", "SUBSURF")
        if subdivision is not None:
            subdivision.subdivision_type = "SIMPLE"
            subdivision.levels = 4
        context.scene.collection.objects.link(ground)
        settings.surface = ground
        return {"FINISHED"}


classes = (
    OBJECT_OT_scatter_tools_scatter,
    OBJECT_OT_scatter_tools_reseed,
    OBJECT_OT_scatter_tools_clear,
    OBJECT_OT_scatter_tools_ground,
)


def register() -> None:
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
