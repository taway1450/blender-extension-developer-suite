"""A nested submodule: it imports the addon's package name."""

import bpy
from bpy.types import Panel, Preferences

from .. import __package__ as base_package


class PREFS_EXT_PT_panel(Panel):
    bl_label = "Preferences"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        if context.preferences is not None:
            self.layout.prop(preferences(context.preferences), "scale")


def preferences(preferences: Preferences):
    return preferences.addons[base_package].preferences


def register():
    bpy.utils.register_class(PREFS_EXT_PT_panel)


def unregister():
    bpy.utils.unregister_class(PREFS_EXT_PT_panel)
