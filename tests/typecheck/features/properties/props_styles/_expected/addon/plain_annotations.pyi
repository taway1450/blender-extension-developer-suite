from typing import Any

from bpy.types import PropertyGroup

class PROPS_STYLES_Plain(PropertyGroup):
    @property
    def count(self) -> int: ...
    @count.setter
    def count(self, value: int) -> None: ...
    @property
    def quoted(self) -> bool: ...
    @quoted.setter
    def quoted(self, value: bool) -> None: ...
    legacy: Any

classes: tuple[type[PROPS_STYLES_Plain]]
