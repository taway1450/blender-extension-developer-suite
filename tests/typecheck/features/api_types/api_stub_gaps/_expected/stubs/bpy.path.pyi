"""Reference stub delta: the frozensets in bpy.path's __all__, and ensure_ext returns its path's type, str or bytes."""

from typing import TypeVar

_AnyStr = TypeVar("_AnyStr", str, bytes)

extensions_image: frozenset[str]
extensions_movie: frozenset[str]
extensions_audio: frozenset[str]
def ensure_ext(filepath: _AnyStr, ext: _AnyStr, *, case_sensitive: bool = False) -> _AnyStr: ...
