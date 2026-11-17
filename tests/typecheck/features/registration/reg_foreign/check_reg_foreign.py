"""Classes registered from a dict's values: the checker gives up following register(), so both operators exist."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def registered() -> None:
    assert_type(bpy.ops.reg_foreign.first(), Result)
    assert_type(bpy.ops.reg_foreign.second(), Result)
