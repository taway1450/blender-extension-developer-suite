"""The types the add-on's code relies on. Blender never imports this file (see ../README.md)."""

from __future__ import annotations

from typing import Literal, assert_type

import bpy
from bpy.types import (
    Collection,
    Context,
    Mesh,
    Object,
    Scene,
    SubsurfModifier,
    bpy_prop_array,
    bpy_prop_collection_idprop,
)
from mathutils import Color, Vector

from .preferences import ScatterToolsPreferences
from .properties import ScatterItem, ScatterSettings

type Result = set[
    Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]
]


def registered_properties(scene: Scene, ob: Object) -> None:
    # demo: properties
    assert_type(scene.scatter_tools, ScatterSettings)
    assert_type(ob.is_scatter_copy, bool)
    scene.scatter_tool  # ty: ignore[missing-attribute]


def property_types(settings: ScatterSettings) -> None:
    assert_type(settings.count, int)
    # demo: property_wrappers
    assert_type(settings.radius, float)
    assert_type(settings.density, float)
    assert_type(settings.distribution, Literal["DISC", "RING", "GRID"])
    assert_type(settings.randomize, set[Literal["ROTATION", "SCALE"]])
    assert_type(settings.scale_range, bpy_prop_array[float])
    assert_type(settings.offset, Vector)
    assert_type(settings.tint, Color)
    assert_type(settings.surface, Object | None)
    assert_type(settings.target_collection, Collection | None)
    assert_type(settings.placed, bpy_prop_collection_idprop[ScatterItem])
    assert_type(settings.placed.add(), ScatterItem)
    assert_type(settings.placed[0].instance, Object | None)
    settings.distribution = "SPIRAL"  # ty: ignore[invalid-assignment]


def preferences(context: Context) -> None:
    prefs = context.preferences.addons[__package__].preferences
    # demo: addon_preferences
    assert_type(prefs, ScatterToolsPreferences)
    assert_type(prefs.default_count, int)


def operator_calls() -> None:
    # demo: operator_calls
    assert_type(bpy.ops.object.scatter_tools_scatter(count=3), Result)
    bpy.ops.object.scatter_tools_scatter("INVOKE_DEFAULT", keep_previous=True)
    bpy.ops.object.scatter_tools_scatter(count="many")  # ty: ignore[invalid-argument-type]
    bpy.ops.object.scatter_tools_scater()  # ty: ignore[missing-attribute]


def constructors(mesh: Mesh) -> None:
    ground = bpy.data.objects.new("Ground", mesh)
    # demo: type_narrowing
    assert_type(ground.data, Mesh)
    subdivision = ground.modifiers.new("Subdivide", "SUBSURF")
    assert_type(subdivision, SubsurfModifier | None)
