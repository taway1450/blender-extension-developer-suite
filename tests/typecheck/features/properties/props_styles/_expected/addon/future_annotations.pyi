from bpy.types import PropertyGroup

class PROPS_STYLES_Future(PropertyGroup):
    @property
    def later(self) -> PROPS_STYLES_Later: ...
    @property
    def factor(self) -> float: ...
    @factor.setter
    def factor(self, value: float) -> None: ...

class PROPS_STYLES_Later(PropertyGroup):
    ratio: float

classes: tuple[type[PROPS_STYLES_Later], type[PROPS_STYLES_Future]]
