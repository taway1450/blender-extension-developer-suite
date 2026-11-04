"""Expected types of PropertyGroup fields, as they are at runtime in Blender."""

from __future__ import annotations

from typing import assert_type

from bpy.types import Object, bpy_prop_array, bpy_prop_collection
from mathutils import Vector

from . import PROPS_ANNOTATIONS_Item, PROPS_ANNOTATIONS_Settings


def instance_values(s: PROPS_ANNOTATIONS_Settings) -> None:
    assert_type(s.count, int)
    assert_type(s.factor, float)
    assert_type(s.enabled, bool)
    assert_type(s.title, str)
    assert_type(s.offset, Vector)  # a vector subtype (TRANSLATION) gives a mathutils.Vector
    assert_type(s.weights, bpy_prop_array[float])  # no subtype: a plain RNA array
    assert_type(s.mode, str)
    assert_type(s.flags, set[str])  # ENUM_FLAG: a set of identifiers
    assert_type(s.target, Object | None)
    assert_type(s.item, PROPS_ANNOTATIONS_Item)  # a PropertyGroup pointer is never None
    assert_type(s.items, bpy_prop_collection[PROPS_ANNOTATIONS_Item])


def collection_methods(s: PROPS_ANNOTATIONS_Settings) -> None:
    assert_type(s.items.add(), PROPS_ANNOTATIONS_Item)
    assert_type(s.items[0], PROPS_ANNOTATIONS_Item)
    for item in s.items:
        assert_type(item, PROPS_ANNOTATIONS_Item)
        assert_type(item.label, str)


def assignments(s: PROPS_ANNOTATIONS_Settings, obj: Object) -> None:
    s.count = 3
    s.factor = 1  # an int is accepted for a float property
    s.target = obj
    s.target = None
    s.offset = (1.0, 2.0, 3.0)
    s.mode = "B"
    s.flags = {"X", "Y"}
    s.count = "3"  # ty: ignore[invalid-assignment]
    s.enabled = "yes"  # ty: ignore[invalid-assignment]
    s.item = None  # ty: ignore[invalid-assignment]
