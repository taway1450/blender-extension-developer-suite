"""Reference stub delta: the key overloads the checker adds for prefs_split."""

from typing import Any, Literal, overload

from prefs_split.settings import PREFS_SPLIT_Preferences

class _prefs_split_addon(Addon):
    preferences: PREFS_SPLIT_Preferences

class Addons:
    @overload
    def __getitem__(self, key: Literal["prefs_split"], /) -> _prefs_split_addon: ...
    @overload
    def __getitem__(self, key: str, /) -> Addon: ...
    @overload
    def __getitem__(self, key: int, /) -> Addon: ...
