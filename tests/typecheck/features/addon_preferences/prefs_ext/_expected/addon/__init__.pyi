"""Reference stub of prefs_ext."""

from typing import Literal

from bpy.types import AddonPreferences, Preferences

from . import helpers as helpers
from .ui import panel as panel

ADDON_ID: str

class PREFS_EXT_Preferences(AddonPreferences):
    scale: float
    mode: Literal["A", "B"]
    enabled: bool

def preferences(preferences: Preferences) -> PREFS_EXT_Preferences: ...
def register() -> None: ...
def unregister() -> None: ...
