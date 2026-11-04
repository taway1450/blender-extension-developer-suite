"""Expected types and rejected mistakes for Operator subclasses."""

from __future__ import annotations

from typing import assert_type

import bpy
from bpy.types import Event, Operator


def operator_members(op: Operator, event: Event) -> None:
    assert_type(op.bl_idname, str)
    assert_type(op.bl_label, str)
    assert_type(op.has_reports, bool)
    event_type: str = event.type  # an enum: the stubs may use a Literal union, which must still be a str
    assert_type(event.mouse_x, int)
    assert_type(event.shift, bool)


def report(op: Operator) -> None:
    op.report({"INFO"}, "ok")
    op.report({"WARNING", "INFO"}, "ok")
    op.report({"NOPE"}, "x")  # ty: ignore[invalid-argument-type]
    op.report("INFO", "x")  # ty: ignore[invalid-argument-type]


def calling_operators() -> None:
    for status in bpy.ops.object.select_all(action="SELECT"):
        status_name: str = status  # a set of return-enum identifiers, e.g. {"FINISHED"}
    bpy.ops.object.select_all(action="EVERYTHING")  # ty: ignore[invalid-argument-type]


class BadOptions(Operator):
    bl_idname = "operator_basics.bad_options"
    bl_label = "Bad options"
    bl_options = {"REGISTR"}  # ty: ignore[invalid-assignment]


class BadSignature(Operator):
    bl_idname = "operator_basics.bad_signature"
    bl_label = "Bad signature"

    def execute(self) -> set[str]:  # ty: ignore[invalid-method-override]
        return {"FINISHED"}
