"""The first component of a module name of a legacy add-on is the add-on's name, however it is split off."""

from __future__ import annotations

from typing import assert_type

from bpy.types import AddonPreferences, Preferences

from .settings import PREFS_SPLIT_Preferences


def literal_key(preferences: Preferences) -> None:
    prefs = preferences.addons["prefs_split"].preferences
    assert_type(prefs, PREFS_SPLIT_Preferences)
    assert_type(prefs.scale, float)


def first_component_keys(preferences: Preferences) -> None:
    assert_type(preferences.addons[__name__.split(".")[0]].preferences, PREFS_SPLIT_Preferences)  # oracle-skip: stock ty types the key as str
    assert_type(preferences.addons[__name__.partition(".")[0]].preferences, PREFS_SPLIT_Preferences)  # oracle-skip: stock ty types the key as str


def other_split_keys(preferences: Preferences) -> None:
    assert_type(preferences.addons[__name__.split(".", 1)[0]].preferences, PREFS_SPLIT_Preferences)  # oracle-skip: stock ty types the key as str
    assert_type(preferences.addons[__name__.split(".", maxsplit=1)[0]].preferences, PREFS_SPLIT_Preferences)  # oracle-skip: stock ty types the key as str
    assert_type(preferences.addons[__name__.split(sep=".")[0]].preferences, PREFS_SPLIT_Preferences)  # oracle-skip: stock ty types the key as str
    assert_type(preferences.addons[__name__.rsplit(".")[0]].preferences, PREFS_SPLIT_Preferences)  # oracle-skip: stock ty types the key as str
    assert_type(preferences.addons[__name__.rsplit(".", 1)[0]].preferences, PREFS_SPLIT_Preferences)  # oracle-skip: stock ty types the key as str
    assert_type(preferences.addons["prefs_split.settings".rpartition(".")[0]].preferences, PREFS_SPLIT_Preferences)  # oracle-skip: stock ty types the key as str
    assert_type(preferences.addons["prefs_split".rsplit(".", 1)[0]].preferences, PREFS_SPLIT_Preferences)  # oracle-skip: stock ty types the key as str
    # Splitting nowhere keeps the whole name, a submodule's, which is not the add-on.
    assert_type(preferences.addons[__name__.split(".", 0)[0]].preferences, AddonPreferences | None)  # bare-ok: the stub type is kept for a key that is not the add-on
