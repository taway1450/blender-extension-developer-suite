from bpy.types import Object, PropertyGroup

class PROPS_CALLBACKS_Settings(PropertyGroup):
    count: int
    label: str
    ratio: float
    target: Object | None
    mode: str
    @property
    def lambda_get(self) -> int: ...

def register() -> None: ...
def unregister() -> None: ...
