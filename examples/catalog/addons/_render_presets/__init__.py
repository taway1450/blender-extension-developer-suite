"""The add-on `declared_dependency` relies on. It is no entry of its own (its name starts with `_`)."""

import bpy
from bpy.props import IntProperty, PointerProperty
from bpy.types import PropertyGroup


class RENDER_PRESETS_Settings(PropertyGroup):
    samples: IntProperty(default=64)


def register():
    bpy.utils.register_class(RENDER_PRESETS_Settings)
    bpy.types.Scene.render_presets = PointerProperty(type=RENDER_PRESETS_Settings)


def unregister():
    del bpy.types.Scene.render_presets
    bpy.utils.unregister_class(RENDER_PRESETS_Settings)
