"""Reference stub delta: the properties props_registered adds to Blender's classes."""

from typing import Literal

from props_registered import PROPS_REGISTERED_Item

class ID:
    reg_id: int
    reg_owner_first: int
    reg_owner_last: int

class Scene:
    reg_owner_first: str
    reg_owner_last: str
    reg_int: int
    reg_mode: Literal["A", "B"]
    @property
    def reg_group(self) -> PROPS_REGISTERED_Item: ...
    @property
    def reg_items(self) -> bpy_prop_collection_idprop[PROPS_REGISTERED_Item]: ...
    reg_object: Object | None
    @property
    def reg_locked(self) -> int: ...

class Object:
    reg_float: float

class Material:
    reg_str: str

class Camera:
    reg_module_level: int

class Collection:
    reg_alias: str

class Image:
    reg_setattr: float

class WindowManager:
    reg_bool: bool

class Bone:
    reg_bone: int

class EditBone:
    reg_edit_bone: int

class PoseBone:
    reg_pose_bone: int

class Node:
    reg_node: int

class NodeSocket:
    reg_socket: int

class ViewLayer:
    reg_view_layer: int

class Strip:
    reg_strip: int
