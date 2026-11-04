"""Properties with callbacks have the same types as without; the callbacks' checks are in __init__.py."""

from __future__ import annotations

from typing import assert_type

from bpy.types import Object

from . import PROPS_CALLBACKS_Settings


def values(s: PROPS_CALLBACKS_Settings) -> None:
    assert_type(s.count, int)
    assert_type(s.ratio, float)
    assert_type(s.target, Object | None)
    assert_type(s.mode, str)  # dynamic items: only str is known
