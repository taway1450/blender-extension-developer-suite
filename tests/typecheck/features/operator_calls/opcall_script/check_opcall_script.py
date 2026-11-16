"""Built-in operators called from a script outside any add-on."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def builtin_from_script() -> None:
    assert_type(bpy.ops.wm.call_menu("INVOKE_DEFAULT", False, name="VIEW3D_MT_add"), Result)
    bpy.ops.wm.call_menu("INVOKE_WRONG")  # ty: ignore[no-matching-overload]
