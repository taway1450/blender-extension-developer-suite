"""A group named like the `bpy.types` class it shadows, as rigify's `ActionSlot` is: in `register()`, `Text` may be
either class."""

import bpy
from bpy.props import CollectionProperty, IntProperty
from bpy.types import PropertyGroup, Text  # noqa: F401 -- shadowed below, on purpose


class Text(PropertyGroup):  # noqa: F811
    value: IntProperty()


def register():
    bpy.utils.register_class(Text)
    bpy.types.Curve.props_id_data_texts = CollectionProperty(type=Text)


def unregister():
    del bpy.types.Curve.props_id_data_texts
    bpy.utils.unregister_class(Text)
