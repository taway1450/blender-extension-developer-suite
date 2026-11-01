"""Example extension: scatter linked copies of the active object around it."""

from __future__ import annotations

import random

import bpy
from bpy.props import FloatProperty, IntProperty, PointerProperty
from bpy.types import Context, Object, Operator, Panel, PropertyGroup
from mathutils import Vector


class SimpleScatterSettings(PropertyGroup):
    count: IntProperty(name="Count", description="Number of copies to create", default=10, min=1, max=1000)
    radius: FloatProperty(name="Radius", description="Maximum distance from the original", default=5.0,
                          min=0.0, unit="LENGTH")
    seed: IntProperty(name="Seed", description="Random seed", default=0, min=0)


def scatter_settings(context: Context) -> SimpleScatterSettings:
    return context.scene.simple_scatter


class OBJECT_OT_simple_scatter(Operator):
    """Scatter linked copies of the active object around it"""

    bl_idname = "object.simple_scatter"
    bl_label = "Scatter Active Object"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: Context) -> bool:
        return context.active_object is not None and context.mode == "OBJECT"

    def execute(self, context: Context) -> set[str]:
        settings = scatter_settings(context)
        source = context.active_object
        assert source is not None
        collection = context.collection or context.scene.collection
        rng = random.Random(settings.seed)

        copies: list[Object] = []
        for _ in range(settings.count):
            copy = source.copy()
            offset = Vector((rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), 0.0)) * settings.radius
            copy.location = source.location + offset
            copy.rotation_euler.z = rng.uniform(0.0, 6.283185)
            collection.objects.link(copy)
            copies.append(copy)

        self.report({"INFO"}, f"Created {len(copies)} copies of {source.name}")
        return {"FINISHED"}


class VIEW3D_PT_simple_scatter(Panel):
    bl_label = "Simple Scatter"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Scatter"

    def draw(self, context: Context) -> None:
        layout = self.layout
        settings = scatter_settings(context)
        column = layout.column(align=True)
        column.prop(settings, "count")
        column.prop(settings, "radius")
        column.prop(settings, "seed")
        layout.operator(OBJECT_OT_simple_scatter.bl_idname, icon="PARTICLES")


classes = (SimpleScatterSettings, OBJECT_OT_simple_scatter, VIEW3D_PT_simple_scatter)


def register() -> None:
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.simple_scatter = PointerProperty(type=SimpleScatterSettings)


def unregister() -> None:
    del bpy.types.Scene.simple_scatter
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
