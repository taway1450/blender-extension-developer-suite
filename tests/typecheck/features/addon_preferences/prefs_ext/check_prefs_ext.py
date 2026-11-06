"""The addon's preferences are its own class wherever the key names the addon."""

from __future__ import annotations

from typing import Literal, assert_type

from bpy.types import AddonPreferences, Preferences

from . import ADDON_ID, PREFS_EXT_Preferences, helpers, preferences
from .ui import panel


def key_spellings(preferences: Preferences) -> None:
    assert_type(preferences.addons[__package__].preferences, PREFS_EXT_Preferences)  # oracle-skip: stock ty types __package__ as str | None
    assert_type(preferences.addons[ADDON_ID].preferences, PREFS_EXT_Preferences)  # oracle-skip: stock ty types __package__ as str | None


def through_functions(prefs: Preferences) -> None:
    assert_type(preferences(prefs), PREFS_EXT_Preferences)  # bare-ok: the return annotation types the call; the checker's part is the helper's return, otherwise invalid-return-type
    assert_type(helpers.preferences(prefs), PREFS_EXT_Preferences)  # bare-ok: the return annotation types the call; the checker's part is the helper's return, otherwise invalid-return-type
    assert_type(panel.preferences(prefs), PREFS_EXT_Preferences)  # bare-ok: the return annotation types the call; the checker's part is the helper's return, otherwise invalid-return-type


def members(preferences: Preferences) -> None:
    prefs = preferences.addons[__package__].preferences  # oracle-skip: stock ty types __package__ as str | None
    assert_type(prefs.scale, float)  # oracle-skip: stock ty types __package__ as str | None
    assert_type(prefs.mode, Literal["A", "B"])  # oracle-skip: stock ty types __package__ as str | None
    prefs.scale = 2.0  # oracle-skip: stock ty types __package__ as str | None
    prefs.scale = "2"  # ty: ignore[invalid-assignment]  # oracle-skip: stock ty types __package__ as str | None  # bare-ok: holds bare because the attribute is missing; the asserts above need the checker
    prefs.missing  # ty: ignore[unresolved-attribute]  # oracle-skip: stock ty types __package__ as str | None  # bare-ok: must stay missing: ty-blender must not add it


def get(preferences: Preferences) -> None:
    addon = preferences.addons.get(__package__)  # oracle-skip: stock ty types __package__ as str | None
    if addon is not None:
        assert_type(addon.preferences, PREFS_EXT_Preferences)  # oracle-skip: stock ty types __package__ as str | None


def other_keys(preferences: Preferences, name: str) -> None:
    assert_type(preferences.addons["other_addon"].preferences, AddonPreferences | None)  # bare-ok: the stub type is kept for another add-on's key
    assert_type(preferences.addons[name].preferences, AddonPreferences | None)  # bare-ok: the stub type is kept for a non-literal key
    # This module's __name__ is the check module, not the addon.
    assert_type(preferences.addons[__name__].preferences, AddonPreferences | None)  # bare-ok: the stub type is kept for a key that is not the add-on
