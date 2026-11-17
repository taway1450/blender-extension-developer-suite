"""The methods annotated `-> set[str]` have the parent's result type for their callers."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

from bpy.types import Context, Event

from . import (
    IMP_OPERATOR_RETURN_OT_follow_on,
    IMP_OPERATOR_RETURN_OT_set_str,
)

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def _(op: IMP_OPERATOR_RETURN_OT_set_str, context: Context, event: Event) -> None:
    assert_type(op.execute(context), Result)
    assert_type(op.invoke(context, event), Result)


def _(op: IMP_OPERATOR_RETURN_OT_follow_on, context: Context, event: Event) -> None:
    assert_type(op.invoke(context, event), Result)
