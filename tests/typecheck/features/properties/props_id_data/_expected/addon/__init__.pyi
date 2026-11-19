from bpy.types import Armature, Material, Mesh, Object, PropertyGroup, Scene, bpy_prop_collection_idprop

class PROPS_ID_DATA_Slot(PropertyGroup):
    value: int
    @property
    def id_data(self) -> Armature: ...
    def siblings(self) -> int: ...

class PROPS_ID_DATA_Inner(PropertyGroup):
    value: int
    @property
    def id_data(self) -> Scene | Object: ...
    def owner(self) -> Scene | Object: ...

class PROPS_ID_DATA_Outer(PropertyGroup):
    @property
    def id_data(self) -> Scene | Object: ...
    @property
    def inner(self) -> PROPS_ID_DATA_Inner: ...
    @property
    def inners(self) -> bpy_prop_collection_idprop[PROPS_ID_DATA_Inner]: ...

class PROPS_ID_DATA_BoneSettings(PropertyGroup):
    value: int
    @property
    def id_data(self) -> Object: ...

class PROPS_ID_DATA_Base(PropertyGroup):
    value: int
    @property
    def id_data(self) -> Scene | Mesh: ...

class PROPS_ID_DATA_Derived(PROPS_ID_DATA_Base):
    extra: int
    @property
    def id_data(self) -> Mesh: ...

class PROPS_ID_DATA_Shared(PropertyGroup):
    value: int
    @property
    def id_data(self) -> Material | Scene: ...

class PROPS_ID_DATA_Unowned(PropertyGroup):
    value: int

classes: tuple[type[PropertyGroup], ...]

def register() -> None: ...
def unregister() -> None: ...
