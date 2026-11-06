"""When the checker cannot follow register(), the preferences are any class that names the add-on."""

from __future__ import annotations

from typing import assert_type

from bpy.types import Preferences

from . import PREFS_DISCOVERED_Full, PREFS_DISCOVERED_Simple


def either(preferences: Preferences) -> None:
    assert_type(preferences.addons[__package__].preferences, PREFS_DISCOVERED_Simple | PREFS_DISCOVERED_Full)  # oracle-skip: stock ty types __package__ as str | None
