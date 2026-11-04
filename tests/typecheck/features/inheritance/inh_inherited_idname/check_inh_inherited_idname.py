"""The operator is the subclass that replaced the parent."""

from __future__ import annotations

from typing import Literal, TypeAlias, assert_type

import bpy
from bpy.types import Scene

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def operator() -> None:
    assert_type(bpy.ops.inh_inherited_idname.run(count=1, label="x"), Result)
