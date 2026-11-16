"""A PropertyGroup found by auto_load, whose register() classmethod assigns its pointer, as Cycles does."""

import bpy
from bpy.props import IntProperty, PointerProperty
from bpy.types import PropertyGroup


class REG_AUTOLOAD_PG_settings(PropertyGroup):
    count: IntProperty()

    @classmethod
    def register(cls):
        bpy.types.Scene.reg_autoload_settings = PointerProperty(type=cls)

    @classmethod
    def unregister(cls):
        del bpy.types.Scene.reg_autoload_settings
