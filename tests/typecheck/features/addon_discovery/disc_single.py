"""Feature test: a legacy single-file add-on (a module with bl_info, not a package)."""

from __future__ import annotations

from typing import Literal, assert_type

import bpy
from bpy.props import IntProperty
from bpy.types import Scene

bl_info = {
    "name": "Feature test: single-file add-on",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


def register():
    bpy.types.Scene.disc_single_marker = IntProperty()


def unregister():
    del bpy.types.Scene.disc_single_marker


def _checks(scene: Scene) -> None:
    # Never called: markers for check:features. A top-level module has the empty string as __package__.
    assert_type(__package__, Literal[""])  # oracle-skip: stock ty types __package__ as str | None
    assert_type(scene.disc_single_marker, int)  # oracle-skip: a single-file add-on has no _expected/ folder
