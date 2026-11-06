"""A property made by an alias, a wrapper or a container has the type of the property it evaluates to."""

from __future__ import annotations

from typing import Any, Literal, assert_type

from bpy.types import Scene, bpy_prop_array
from mathutils import Color, Vector

from . import WRAP_VALUES_Settings


def exact(s: WRAP_VALUES_Settings) -> None:
    assert_type(s.common_a, int)
    assert_type(s.common_b, int)
    assert_type(s.alias, float)
    assert_type(s.partial_color, Color)
    assert_type(s.partial_override, bpy_prop_array[float])
    assert_type(s.from_dict, float)
    assert_type(s.from_dict_str, str)
    assert_type(s.from_tuple, int)
    assert_type(s.from_tuple_bool, bool)


def wrappers(s: WRAP_VALUES_Settings) -> None:
    assert_type(s.wrapped, Color)
    assert_type(s.wrapped_size, Vector)
    assert_type(s.wrapped_kwargs, Color)
    assert_type(s.wrapped_enum, Literal["A", "B"])


def partly_known(s: WRAP_VALUES_Settings) -> None:
    assert_type(s.either, float | int)
    assert_type(s.unknown_options, Any)  # bare-ok: unknown options fall back to Any
    assert_type(s.scalar_unknown_options, int)
    assert_type(s.opaque, Any)  # bare-ok: an opaque value falls back to Any


def registered(scene: Scene) -> None:
    assert_type(scene.wrap_values_common, int)
    assert_type(scene.wrap_values_color, Color)
