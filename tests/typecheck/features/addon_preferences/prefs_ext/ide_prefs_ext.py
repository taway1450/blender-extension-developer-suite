"""What the editor shows for addon preferences (check:ide; never imported).

The code under a ^completion marker is unfinished, as the user types it; check:features does not check ide_*.py
files, so the errors it causes do not count.
"""

from __future__ import annotations

from bpy.types import Preferences


def preferences_members(preferences: Preferences) -> None:
    preferences.addons[__package__].preferences.sc
    #                                             ^completion scale
    preferences.addons[__package__].preferences
    #                               ^hover-contains "PREFS_EXT_Preferences"


def package() -> None:
    __package__
    # ^hover-contains "prefs_ext"
