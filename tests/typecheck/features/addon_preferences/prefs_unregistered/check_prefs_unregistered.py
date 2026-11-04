"""Without registration the preferences keep the stub type."""

from __future__ import annotations

from typing import assert_type

from bpy.types import AddonPreferences, Preferences


def not_registered(preferences: Preferences) -> None:
    assert_type(preferences.addons[__package__].preferences, AddonPreferences | None)  # oracle-skip: stock ty types __package__ as str | None
