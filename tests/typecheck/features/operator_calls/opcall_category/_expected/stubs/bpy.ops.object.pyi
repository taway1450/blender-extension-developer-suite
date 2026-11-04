"""Reference stub delta: the operator the addon adds to bpy.ops.object."""

from collections.abc import Sequence
from typing import Literal, TypeAlias, TypedDict

from bpy.types import Struct
from mathutils import Matrix, Vector

_ExecutionContext: TypeAlias = Literal["INVOKE_DEFAULT", "INVOKE_REGION_WIN", "INVOKE_REGION_CHANNELS", "INVOKE_REGION_PREVIEW", "INVOKE_AREA", "INVOKE_SCREEN", "EXEC_DEFAULT", "EXEC_REGION_WIN", "EXEC_REGION_CHANNELS", "EXEC_REGION_PREVIEW", "EXEC_AREA", "EXEC_SCREEN"]

class _opcall_category_scale_operator:
    def __call__(self, execution_context: _ExecutionContext = ..., undo: bool = ..., /, *, factor: float = ...) -> set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]: ...
    def poll(self, execution_context: _ExecutionContext = ..., /) -> bool: ...
    def idname(self) -> Literal["OBJECT_OT_opcall_category_scale"]: ...
    def idname_py(self) -> Literal["object.opcall_category_scale"]: ...
    def get_rna_type(self) -> Struct: ...

opcall_category_scale: _opcall_category_scale_operator
