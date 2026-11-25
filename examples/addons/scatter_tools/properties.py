"""The scatter settings stored on the scene, and what a scatter run leaves behind."""

from __future__ import annotations

import math

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
)
from bpy.types import Collection, Object, PropertyGroup

DISTRIBUTIONS = (
    ("DISC", "Disc", "Fill a disc around the source"),
    ("RING", "Ring", "Place the copies on a circle"),
    ("GRID", "Grid", "Place the copies on a square grid"),
)


# demo: property_wrappers
def length(name: str, default: float, description: str = ""):
    """A length in scene units that cannot be negative."""
    return FloatProperty(
        name=name, description=description, default=default, min=0.0, unit="LENGTH"
    )


def mark_dirty(self, context):
    self.preview_dirty = True


def is_mesh_object(self, candidate):
    return candidate.type == "MESH"


def get_density(self):
    area = math.pi * self.radius**2
    return self.count / area if area else 0.0


def set_density(self, value):
    self.count = max(1, round(value * math.pi * self.radius**2))


class ScatterItem(PropertyGroup):
    """One copy a scatter run placed; its name is the copy's name."""

    instance: PointerProperty(type=Object)


class ScatterSettings(PropertyGroup):
    # demo: properties
    count: IntProperty(
        name="Count",
        description="Number of copies to create",
        default=10,
        min=1,
        max=1000,
        update=mark_dirty,
    )
    radius: length("Radius", 5.0, "Maximum distance from the source")
    density: FloatProperty(
        name="Density",
        description="Copies per square unit; changes the count",
        get=get_density,
        set=set_density,
    )
    seed: IntProperty(name="Seed", default=0, min=0, update=mark_dirty)
    distribution: EnumProperty(name="Distribution", items=DISTRIBUTIONS, default="DISC")
    randomize: EnumProperty(
        name="Randomize",
        items=(
            ("ROTATION", "Rotation", "Turn every copy around its Z axis"),
            ("SCALE", "Scale", "Scale every copy within the scale range"),
        ),
        options={"ENUM_FLAG"},
        default={"ROTATION"},
    )
    scale_range: FloatVectorProperty(
        name="Scale Range", size=2, default=(0.8, 1.2), min=0.01
    )
    offset: FloatVectorProperty(name="Offset", subtype="TRANSLATION")
    tint: FloatVectorProperty(
        name="Tint", subtype="COLOR", default=(1.0, 1.0, 1.0), min=0.0, max=1.0
    )
    surface: PointerProperty(
        name="Surface",
        description="Mesh object the copies are dropped onto",
        type=Object,
        poll=is_mesh_object,
    )
    target_collection: PointerProperty(name="Collection", type=Collection)
    placed: CollectionProperty(type=ScatterItem)
    active_index: IntProperty()
    preview_dirty: BoolProperty(options={"HIDDEN"})


classes = (ScatterItem, ScatterSettings)


def register() -> None:
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.scatter_tools = PointerProperty(type=ScatterSettings)
    bpy.types.Object.is_scatter_copy = BoolProperty(
        name="Scatter Copy", description="Scatter Tools created this object"
    )


def unregister() -> None:
    del bpy.types.Object.is_scatter_copy
    del bpy.types.Scene.scatter_tools
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
