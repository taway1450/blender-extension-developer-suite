"""Feature test: PropertyGroup fields declared with bpy.props annotations (info_overview.rst, "Properties")."""

from __future__ import annotations

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, FloatVectorProperty,
                       IntProperty, PointerProperty, StringProperty)
from bpy.types import PropertyGroup


class PROPS_ANNOTATIONS_Item(PropertyGroup):
    label: StringProperty(name="Label")


class PROPS_ANNOTATIONS_Settings(PropertyGroup):
    count: IntProperty(name="Count", default=1, min=0)
    factor: FloatProperty(name="Factor", default=0.5)
    enabled: BoolProperty(name="Enabled")
    title: StringProperty(name="Title")
    offset: FloatVectorProperty(name="Offset", subtype="TRANSLATION", size=3)
    weights: FloatVectorProperty(name="Weights", size=3)
    mode: EnumProperty(name="Mode", items=[("A", "A", ""), ("B", "B", "")])
    flags: EnumProperty(name="Flags", items=[("X", "X", ""), ("Y", "Y", "")], options={"ENUM_FLAG"})
    target: PointerProperty(name="Target", type=bpy.types.Object)
    item: PointerProperty(type=PROPS_ANNOTATIONS_Item)
    items: CollectionProperty(type=PROPS_ANNOTATIONS_Item)


classes = (PROPS_ANNOTATIONS_Item, PROPS_ANNOTATIONS_Settings)


def register() -> None:
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
