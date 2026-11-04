"""Expected types when reading extension preferences."""

from __future__ import annotations

from typing import assert_type

from bpy.types import Addon, AddonPreferences, Context

from . import ADDON_PREFERENCES_Prefs, get_prefs


def lookup(context: Context) -> None:
    addon = context.preferences.addons["props_annotations"]
    assert_type(addon, Addon)
    assert_type(addon.module, str)
    # None for add-ons without preferences (checked in Blender 5.4); the stubs can only know the base class.
    assert_type(addon.preferences, AddonPreferences | None)


def own_preferences(context: Context) -> None:
    prefs = get_prefs(context)
    assert_type(prefs, ADDON_PREFERENCES_Prefs)
    assert_type(prefs.export_path, str)
    assert_type(prefs.verbose, bool)
