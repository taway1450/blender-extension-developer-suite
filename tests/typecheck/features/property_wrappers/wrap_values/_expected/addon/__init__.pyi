from typing import Any, Literal

from bpy.types import PropertyGroup, bpy_prop_array
from mathutils import Color, Vector

class WRAP_VALUES_Settings(PropertyGroup):
    common_a: int
    common_b: int
    alias: float
    partial_color: Color
    partial_override: bpy_prop_array[float]
    from_dict: float
    from_dict_str: str
    from_tuple: int
    from_tuple_bool: bool
    wrapped: Color
    wrapped_size: Vector
    wrapped_kwargs: Color
    wrapped_enum: Literal["A", "B"]
    either: float | int
    unknown_options: Any
    unknown_pointer: Any
    scalar_unknown_options: int
    opaque: Any

def register() -> None: ...
def unregister() -> None: ...
