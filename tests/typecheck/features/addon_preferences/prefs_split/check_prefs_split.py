"""The first component of a module name of a legacy add-on is the add-on's name."""

from __future__ import annotations

from typing import assert_type

from bpy.types import Preferences

from .settings import PREFS_SPLIT_Preferences


def literal_key(preferences: Preferences) -> None:
    prefs = preferences.addons["prefs_split"].preferences
    assert_type(prefs, PREFS_SPLIT_Preferences)
    assert_type(prefs.scale, float)


def first_component_keys(preferences: Preferences) -> None:
    assert_type(preferences.addons[__name__.split(".")[0]].preferences, PREFS_SPLIT_Preferences)  # oracle-skip: stock ty types the key as str
    assert_type(preferences.addons[__name__.partition(".")[0]].preferences, PREFS_SPLIT_Preferences)  # oracle-skip: stock ty types the key as str
