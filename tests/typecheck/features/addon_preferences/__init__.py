"""Feature test: extension preferences, as in the extension docs ("Add-ons", "User Preferences")."""

from __future__ import annotations

from typing import cast

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import AddonPreferences, Context


class ADDON_PREFERENCES_Prefs(AddonPreferences):
    bl_idname = __package__

    export_path: StringProperty(name="Export path", subtype="DIR_PATH")
    verbose: BoolProperty(name="Verbose")

    def draw(self, context: Context) -> None:
        layout = self.layout
        layout.prop(self, "export_path")
        layout.prop(self, "verbose")


def get_prefs(context: Context) -> ADDON_PREFERENCES_Prefs:
    # Addon.preferences is the registered AddonPreferences subclass (None for add-ons without one).
    return cast(ADDON_PREFERENCES_Prefs, context.preferences.addons[__package__].preferences)


def register() -> None:
    bpy.utils.register_class(ADDON_PREFERENCES_Prefs)


def unregister() -> None:
    bpy.utils.unregister_class(ADDON_PREFERENCES_Prefs)
