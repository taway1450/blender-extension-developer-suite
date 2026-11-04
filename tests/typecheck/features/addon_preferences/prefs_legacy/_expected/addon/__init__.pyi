"""Reference stub of prefs_legacy."""

from typing import Any, Literal

from bpy.types import AddonPreferences

bl_info: dict[str, Any]

class PREFS_LEGACY_Preferences(AddonPreferences):
    scale: float
    mode: Literal["A", "B"]
    enabled: bool

def register() -> None: ...
def unregister() -> None: ...
