"""Feature test: preferences of a legacy add-on (bl_info): the key is __name__ (or the literal module name)."""

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty
from bpy.types import AddonPreferences

bl_info = {
    "name": "Feature test: preferences of a legacy add-on",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


class PREFS_LEGACY_Preferences(AddonPreferences):
    bl_idname = __name__

    scale: FloatProperty(default=1.0)
    mode: EnumProperty(items=[("A", "A", ""), ("B", "B", "")])
    enabled: BoolProperty()

    def draw(self, context):
        self.layout.prop(self, "scale")


def register():
    bpy.utils.register_class(PREFS_LEGACY_Preferences)


def unregister():
    bpy.utils.unregister_class(PREFS_LEGACY_Preferences)
