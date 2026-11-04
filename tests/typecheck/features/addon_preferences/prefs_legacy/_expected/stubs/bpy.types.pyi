"""Reference stub delta: the key overloads the checker adds for prefs_legacy."""

from typing import Any, Literal, overload

from prefs_legacy import PREFS_LEGACY_Preferences

class _prefs_legacy_addon(Addon):
    preferences: PREFS_LEGACY_Preferences

class Addons:
    @overload
    def __getitem__(self, key: Literal["prefs_legacy"], /) -> _prefs_legacy_addon: ...
    @overload
    def __getitem__(self, key: str, /) -> Addon: ...
    @overload
    def __getitem__(self, key: int, /) -> Addon: ...
