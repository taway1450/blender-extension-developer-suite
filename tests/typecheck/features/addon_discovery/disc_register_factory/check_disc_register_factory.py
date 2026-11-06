"""The assigned register() is the entry point: the operator it registers is in bpy.ops."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, assert_type

import bpy

from . import register, unregister


def entry_points() -> None:
    assert_type(register, Callable[[], None])  # bare-ok: the stubs type the factory's result; the checker must not change it
    assert_type(unregister, Callable[[], None])  # bare-ok: the stubs type the factory's result; the checker must not change it


def registered() -> None:
    assert_type(bpy.ops.disc_register_factory.run(count=1),
                set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]])
    bpy.ops.disc_register_factory.run(count="1")  # ty: ignore[invalid-argument-type]
