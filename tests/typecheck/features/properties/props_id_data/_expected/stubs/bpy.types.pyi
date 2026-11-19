"""Reference stub delta: every data-block is its own id_data, and the properties props_id_data registers."""

from typing import Self

from props_id_data.shadowed import Text as ShadowedText
from props_id_data import (PROPS_ID_DATA_Base, PROPS_ID_DATA_BoneSettings, PROPS_ID_DATA_Derived, PROPS_ID_DATA_Outer,
                           PROPS_ID_DATA_Shared, PROPS_ID_DATA_Slot)

class ID:
    @property
    def id_data(self) -> Self: ...

class Armature:
    @property
    def props_id_data_slots(self) -> bpy_prop_collection_idprop[PROPS_ID_DATA_Slot]: ...

class Scene:
    @property
    def props_id_data_outer(self) -> PROPS_ID_DATA_Outer: ...
    @property
    def props_id_data_base(self) -> PROPS_ID_DATA_Base: ...
    @property
    def props_id_data_shared(self) -> PROPS_ID_DATA_Shared: ...

class Object:
    @property
    def props_id_data_outer(self) -> PROPS_ID_DATA_Outer: ...

class PoseBone:
    @property
    def props_id_data_bone(self) -> PROPS_ID_DATA_BoneSettings: ...

class Mesh:
    @property
    def props_id_data_derived(self) -> PROPS_ID_DATA_Derived: ...

class Material:
    @property
    def props_id_data_shared(self) -> PROPS_ID_DATA_Shared: ...

class Curve:
    @property
    def props_id_data_texts(self) -> bpy_prop_collection_idprop[ShadowedText]: ...
