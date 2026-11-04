"""Reference stub delta: the idname overloads the checker adds, for the addon's operator and for Blender's own."""

from typing import Any, Literal, overload

class _opprops_idnames_step_properties(bpy_struct):
    factor: float

class _object_select_all_properties(bpy_struct):
    action: Literal["TOGGLE", "SELECT", "DESELECT", "INVERT"]

class _mesh_primitive_cube_add_properties(bpy_struct):
    size: float
    calc_uvs: bool

class UILayout:
    @overload
    def operator(self, operator: Literal["opprops_idnames.step", "OPPROPS_IDNAMES_OT_step"], **kwargs: Any) -> _opprops_idnames_step_properties: ...
    @overload
    def operator(self, operator: Literal["object.select_all", "OBJECT_OT_select_all"], **kwargs: Any) -> _object_select_all_properties: ...
    @overload
    def operator(self, operator: Literal["mesh.primitive_cube_add", "MESH_OT_primitive_cube_add"], **kwargs: Any) -> _mesh_primitive_cube_add_properties: ...
