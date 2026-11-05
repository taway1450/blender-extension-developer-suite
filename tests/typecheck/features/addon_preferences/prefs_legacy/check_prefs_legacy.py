"""The literal module name names a legacy add-on."""

from __future__ import annotations

from typing import Literal, assert_type

from bpy.types import AddonPreferences, Preferences

from . import PREFS_LEGACY_Preferences


def literal_key(preferences: Preferences) -> None:
    prefs = preferences.addons["prefs_legacy"].preferences
    assert_type(prefs, PREFS_LEGACY_Preferences)
    assert_type(prefs.scale, float)
    assert_type(prefs.mode, Literal["A", "B"])
    prefs.mode = "C"  # ty: ignore[invalid-assignment]  # bare-ok: holds bare because the attribute is missing; the asserts above need the checker


def package_key(preferences: Preferences) -> None:
    assert_type(preferences.addons[__package__].preferences, PREFS_LEGACY_Preferences)  # oracle-skip: stock ty types __package__ as str | None


def other_keys(preferences: Preferences) -> None:
    assert_type(preferences.addons["prefs_ext"].preferences, AddonPreferences | None)  # bare-ok: the stub type is kept for another add-on's key
