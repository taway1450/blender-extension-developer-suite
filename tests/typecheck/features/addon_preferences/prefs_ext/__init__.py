"""Feature test: preferences.addons[<this addon>].preferences is the addon's own AddonPreferences class,
not AddonPreferences | None, when the key names this addon: __package__ (in __init__.py and in submodules), a
constant holding it, __name__ in __init__.py, __name__.rpartition(".")[0] in a direct submodule and
`from .. import __package__` in a nested one. Other keys keep the stub type."""

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty
from bpy.types import AddonPreferences, Preferences

from . import helpers
from .ui import panel

ADDON_ID = __package__


class PREFS_EXT_Preferences(AddonPreferences):
    bl_idname = __package__

    scale: FloatProperty(default=1.0)
    mode: EnumProperty(items=[("A", "A", ""), ("B", "B", "")])
    enabled: BoolProperty()

    def draw(self, context):
        self.layout.prop(self, "scale")


def preferences(preferences: Preferences):
    return preferences.addons[__package__].preferences


def register():
    bpy.utils.register_class(PREFS_EXT_Preferences)
    helpers.register()
    panel.register()


def unregister():
    panel.unregister()
    helpers.unregister()
    bpy.utils.unregister_class(PREFS_EXT_Preferences)
