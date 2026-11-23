from bpy.types import PropertyGroup

class PROPS_ID_DATA_OPAQUE_Group(PropertyGroup):
    value: int

def register() -> None: ...
def unregister() -> None: ...
