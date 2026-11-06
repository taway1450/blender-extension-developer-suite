"""Calls of an addon operator: keyword arguments from its properties, positional execution context and undo."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy
from bpy.types import Struct
from mathutils import Matrix, Vector

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def call_forms() -> None:
    assert_type(bpy.ops.opcall_basic.all(), Result)
    assert_type(bpy.ops.opcall_basic.empty(), Result)
    bpy.ops.opcall_basic.all("INVOKE_DEFAULT")
    bpy.ops.opcall_basic.all("INVOKE_REGION_WIN")
    bpy.ops.opcall_basic.all("INVOKE_REGION_CHANNELS")
    bpy.ops.opcall_basic.all("INVOKE_REGION_PREVIEW")
    bpy.ops.opcall_basic.all("INVOKE_AREA")
    bpy.ops.opcall_basic.all("INVOKE_SCREEN")
    bpy.ops.opcall_basic.all("EXEC_DEFAULT")
    bpy.ops.opcall_basic.all("EXEC_REGION_WIN")
    bpy.ops.opcall_basic.all("EXEC_REGION_CHANNELS")
    bpy.ops.opcall_basic.all("EXEC_REGION_PREVIEW")
    bpy.ops.opcall_basic.all("EXEC_AREA")
    bpy.ops.opcall_basic.all("EXEC_SCREEN")
    bpy.ops.opcall_basic.all("EXEC_DEFAULT", True)
    bpy.ops.opcall_basic.all("EXEC_DEFAULT", False, int_value=1)
    assert_type(bpy.ops.opcall_basic.all(False), Result)  # the undo flag alone
    bpy.ops.opcall_basic.all(True, int_value=1)
    stored = bpy.ops.opcall_basic.all
    assert_type(stored(int_value=1), Result)


def wrong_call_forms() -> None:
    bpy.ops.opcall_basic.all("NOPE")  # ty: ignore[no-matching-overload]
    bpy.ops.opcall_basic.all("EXEC_DEFAULT", True, 1)  # ty: ignore[no-matching-overload]
    bpy.ops.opcall_basic.all(True, "EXEC_DEFAULT")  # ty: ignore[invalid-argument-type]
    bpy.ops.opcall_basic.all(execution_context="EXEC_DEFAULT")  # ty: ignore[no-matching-overload]
    bpy.ops.opcall_basic.empty(int_value=1)  # ty: ignore[no-matching-overload]
    bpy.ops.opcall_basic.all(unknown=1)  # ty: ignore[no-matching-overload]


def valid_arguments(vector: Vector, matrix: Matrix) -> None:
    bpy.ops.opcall_basic.all(int_value=1, float_value=1.5, bool_value=True, string_value="text")
    bpy.ops.opcall_basic.all(float_value=1)  # an int is a float
    bpy.ops.opcall_basic.all(enum_value="B", flag_value={"A", "B"})
    bpy.ops.opcall_basic.all(flag_value=set())
    bpy.ops.opcall_basic.all(dynamic_value="anything")  # the items are only known when the operator runs
    bpy.ops.opcall_basic.all(vector_value=(1.0, 2.0, 3.0), int_vector_value=[1, 2], bool_vector_value=(True, False))
    bpy.ops.opcall_basic.all(vector_value=vector)
    bpy.ops.opcall_basic.all(matrix_value=((1.0, 0.0), (0.0, 1.0)))
    bpy.ops.opcall_basic.all(matrix_value=matrix)
    bpy.ops.opcall_basic.all(group_value={"count": 3})
    bpy.ops.opcall_basic.all(group_value={})
    bpy.ops.opcall_basic.all(items_value=[{"name": "a", "count": 1}, {"name": "b", "count": 2}])
    bpy.ops.opcall_basic.all(items_value=[])
    bpy.ops.opcall_basic.all(hidden_value=1)


def invalid_arguments() -> None:
    bpy.ops.opcall_basic.all(int_value=1.5)  # ty: ignore[invalid-argument-type]
    bpy.ops.opcall_basic.all(int_value="1")  # ty: ignore[invalid-argument-type]
    bpy.ops.opcall_basic.all(string_value=1)  # ty: ignore[invalid-argument-type]
    bpy.ops.opcall_basic.all(enum_value="C")  # ty: ignore[invalid-argument-type]
    bpy.ops.opcall_basic.all(flag_value="A")  # ty: ignore[invalid-argument-type]
    bpy.ops.opcall_basic.all(flag_value=["A"])  # ty: ignore[invalid-argument-type]
    bpy.ops.opcall_basic.all(flag_value={"C"})  # ty: ignore[invalid-argument-type]
    bpy.ops.opcall_basic.all(vector_value="abc")  # ty: ignore[invalid-argument-type]
    bpy.ops.opcall_basic.all(matrix_value=(1.0, 0.0, 0.0, 1.0))  # ty: ignore[invalid-argument-type]
    bpy.ops.opcall_basic.all(group_value={"count": "3"})  # ty: ignore[invalid-argument-type]
    bpy.ops.opcall_basic.all(items_value=[{"count": 1}])  # ty: ignore[invalid-argument-type, missing-typed-dict-key]


def dropped_properties() -> None:
    bpy.ops.opcall_basic.dropped(before=1)
    bpy.ops.opcall_basic.dropped(target=None)  # ty: ignore[no-matching-overload]
    bpy.ops.opcall_basic.dropped(after=1)  # ty: ignore[no-matching-overload]
    bpy.ops.opcall_basic.dropped_group(before=1)
    bpy.ops.opcall_basic.dropped_group(group={})  # ty: ignore[no-matching-overload]
    bpy.ops.opcall_basic.dropped_group(after=1)  # ty: ignore[no-matching-overload]


def operator_functions() -> None:
    assert_type(bpy.ops.opcall_basic.all.poll(), bool)
    assert_type(bpy.ops.opcall_basic.all.poll("EXEC_DEFAULT"), bool)
    assert_type(bpy.ops.opcall_basic.all.idname(), Literal["OPCALL_BASIC_OT_all"])
    assert_type(bpy.ops.opcall_basic.all.idname_py(), Literal["opcall_basic.all"])
    assert_type(bpy.ops.opcall_basic.all.get_rna_type(), Struct)


def unknown_operators() -> None:
    bpy.ops.opcall_basic.missing  # ty: ignore[unresolved-attribute]  # bare-ok: must stay missing: ty-blender must not add it
    bpy.ops.opcall_basic.OPCALL_BASIC_OT_all  # ty: ignore[unresolved-attribute]  # bare-ok: must stay missing: ty-blender must not add it
