"""A direct submodule: its package name is __name__ without the last part."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bpy.types import Preferences

if TYPE_CHECKING:
    from . import PREFS_EXT_Preferences


def preferences(preferences: Preferences) -> PREFS_EXT_Preferences:
    return preferences.addons[__name__.rpartition(".")[0]].preferences


def register():
    pass


def unregister():
    pass
