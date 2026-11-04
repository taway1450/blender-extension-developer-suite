from bpy.types import PropertyGroup

# Instance-only attributes (properties) so that class-level access is an error, as at runtime.
class CountMixin:
    @property
    def count(self) -> int: ...
    @count.setter
    def count(self, value: int) -> None: ...

class LabelMixin:
    @property
    def label(self) -> str: ...
    @label.setter
    def label(self, value: str) -> None: ...

class PROPS_STYLES_Base(PropertyGroup):
    @property
    def base_value(self) -> int: ...
    @base_value.setter
    def base_value(self, value: int) -> None: ...

class PROPS_STYLES_Child(PROPS_STYLES_Base):
    child_value: float

class PROPS_STYLES_Override(PROPS_STYLES_Base):
    @property  # type: ignore[override]
    def base_value(self) -> str: ...
    @base_value.setter
    def base_value(self, value: str) -> None: ...

class PROPS_STYLES_MixinFirst(CountMixin, LabelMixin, PropertyGroup):
    own: float

class PROPS_STYLES_MixinLast(PropertyGroup, CountMixin): ...

classes: tuple[type[PropertyGroup], ...]
