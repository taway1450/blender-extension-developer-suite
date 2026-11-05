"""A macro takes the properties of its steps, one dict per step."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy


Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def macro_call() -> None:
    assert_type(bpy.ops.opcall_macro.combo(), Result)
    bpy.ops.opcall_macro.combo(OPCALL_MACRO_OT_step={"amount": 2}, OPCALL_MACRO_OT_label={"text": "x"})
    bpy.ops.opcall_macro.combo(OPCALL_MACRO_OT_step={"amount": "2"})  # ty: ignore[invalid-argument-type]
    bpy.ops.opcall_macro.combo(amount=2)  # ty: ignore[unknown-argument]
    assert_type(bpy.ops.opcall_macro.combo.idname(), Literal["OPCALL_MACRO_OT_combo"])
