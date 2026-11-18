"""Reference stub delta: a message bus key is a property, a struct or its type, a (struct type, property name) pair,
or a math value with an owner (obj.location)."""

from collections.abc import Callable
from typing import Any, Literal

from bpy.types import Struct, bpy_prop, bpy_struct
from mathutils import Color, Euler, Matrix, Quaternion, Vector

def subscribe_rna(*, key: bpy_prop | bpy_struct | type[bpy_struct] | tuple[type[bpy_struct] | Struct, str] | Vector | Matrix | Euler | Quaternion | Color, owner: Any, args: tuple, notify: Callable[..., None], options: set[Literal['PERSISTENT']] = set()) -> None: ...
