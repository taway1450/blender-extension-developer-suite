"""Reference stub delta: the idname overloads the checker adds, for the addon's operator and for Blender's own; a
conditional idname gives the union of both operators' properties."""

from collections.abc import Sequence
from typing import Any, Literal, overload

class _opprops_idnames_step_properties(bpy_struct):
    factor: float

class _opprops_idnames_odd_properties(bpy_struct):
    steps: float

class _object_select_all_properties(bpy_struct):
    action: Literal["TOGGLE", "SELECT", "DESELECT", "INVERT"]

class _mesh_primitive_cube_add_properties(bpy_struct):
    size: float
    calc_uvs: bool

class _wm_owner_disable_properties(bpy_struct):
    owner_id: str

class _wm_owner_enable_properties(bpy_struct):
    owner_id: str

class _transform_mirror_properties(bpy_struct):
    @property
    def constraint_axis(self) -> bpy_prop_array[bool]: ...
    @constraint_axis.setter
    def constraint_axis(self, value: Sequence[bool]) -> None: ...

class _image_resize_properties(bpy_struct):
    size: bpy_prop_array[int]

class _image_new_properties(bpy_struct):
    color: bpy_prop_array[float]

class UILayout:
    @overload
    def operator(self, operator: Literal["opprops_idnames.step", "OPPROPS_IDNAMES_OT_step"], **kwargs: Any) -> _opprops_idnames_step_properties: ...
    @overload
    def operator(self, operator: Literal["opprops_idnames_ot_odd.run", "OPPROPS_IDNAMES_OT_ODD_OT_run"], **kwargs: Any) -> _opprops_idnames_odd_properties: ...
    @overload
    def operator(self, operator: Literal["opprops_idnames.step", "opprops_idnames_ot_odd.run"], **kwargs: Any) -> _opprops_idnames_step_properties | _opprops_idnames_odd_properties: ...
    @overload
    def operator(self, operator: Literal["object.select_all", "OBJECT_OT_select_all"], **kwargs: Any) -> _object_select_all_properties: ...
    @overload
    def operator(self, operator: Literal["mesh.primitive_cube_add", "MESH_OT_primitive_cube_add"], **kwargs: Any) -> _mesh_primitive_cube_add_properties: ...
    @overload
    def operator(self, operator: Literal["wm.owner_disable", "WM_OT_owner_disable"], **kwargs: Any) -> _wm_owner_disable_properties: ...
    @overload
    def operator(self, operator: Literal["wm.owner_enable", "WM_OT_owner_enable"], **kwargs: Any) -> _wm_owner_enable_properties: ...
    @overload
    def operator(self, operator: Literal["wm.owner_disable", "wm.owner_enable"], **kwargs: Any) -> _wm_owner_disable_properties | _wm_owner_enable_properties: ...
    @overload
    def operator(self, operator: Literal["transform.mirror", "TRANSFORM_OT_mirror"], **kwargs: Any) -> _transform_mirror_properties: ...
    @overload
    def operator(self, operator: Literal["image.resize", "IMAGE_OT_resize"], **kwargs: Any) -> _image_resize_properties: ...
    @overload
    def operator(self, operator: Literal["image.new", "IMAGE_OT_new"], **kwargs: Any) -> _image_new_properties: ...
