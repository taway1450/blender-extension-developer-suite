"""Feature test: preferences of a legacy add-on whose class sits in a submodule and takes the add-on's name from
its own module name: __name__.split(".")[0] (or .partition(".")[0]) is the first component, the add-on's name."""

from typing import assert_type

import bpy

from . import settings

bl_info = {
    "name": "Feature test: preferences named by the first module name component",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


def register():
    bpy.utils.register_class(settings.PREFS_SPLIT_Preferences)
    # Read once the class is registered, as ui_translate loads its stored settings (the add-on is only in
    # `addons` when it is enabled through the preferences, not when its module is registered directly).
    if __name__ in bpy.context.preferences.addons:
        prefs = bpy.context.preferences.addons[__name__].preferences
        assert_type(prefs, settings.PREFS_SPLIT_Preferences)
        prefs.scale = 2.0


def root_rsplit_key(preferences: bpy.types.Preferences) -> None:
    # In the root module, `rsplit` finds no dot and keeps the whole name, the add-on's.
    assert_type(preferences.addons[__name__.rsplit(".", 1)[0]].preferences, settings.PREFS_SPLIT_Preferences)  # oracle-skip: stock ty types the key as str


def unregister():
    bpy.utils.unregister_class(settings.PREFS_SPLIT_Preferences)
