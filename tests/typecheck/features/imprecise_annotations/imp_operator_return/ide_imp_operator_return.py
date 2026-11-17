"""Hover shows the parent's result type on a method annotated `-> set[str]`."""

from bpy.types import Context

from . import IMP_OPERATOR_RETURN_OT_set_str


def _(op: IMP_OPERATOR_RETURN_OT_set_str, context: Context) -> None:
    op.execute(context)
    #  ^hover-contains "set[Literal["
