from bpy.types import Object, PropertyGroup

class PROPS_CALLBACKS_Settings(PropertyGroup):
    count: int
    label: str
    ratio: float
    target: Object | None
    mode: str

def register() -> None: ...
def unregister() -> None: ...
