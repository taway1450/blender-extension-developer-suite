"""Reference stub: what the checker should see in reg_classmethod."""

from bpy.types import PropertyGroup

class REG_CLASSMETHOD_PG_object(PropertyGroup):
    weight: int

class REG_CLASSMETHOD_PG_scene(PropertyGroup):
    count: int
    @classmethod
    def register(cls) -> None: ...
    @classmethod
    def unregister(cls) -> None: ...

class REG_CLASSMETHOD_PG_never(PropertyGroup):
    @classmethod
    def register(cls) -> None: ...
    @classmethod
    def unregister(cls) -> None: ...

def register() -> None: ...
def unregister() -> None: ...
