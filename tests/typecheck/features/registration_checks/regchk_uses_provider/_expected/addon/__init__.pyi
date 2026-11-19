from bpy.types import PropertyGroup

class REGCHK_USES_PROVIDER_Settings(PropertyGroup):
    samples: int

def register() -> None: ...
def unregister() -> None: ...
