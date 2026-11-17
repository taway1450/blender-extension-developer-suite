"""Registered properties in a script outside any add-on (a startup module, a template, a doc example, a test). Blender
registers them whichever script runs the assignment, so the file's own registrations, at module level or in any
function, give the attributes in that file, and its ``del``s are accepted. Another such file's registrations stay
unknown here: nothing says the two scripts run together."""

from __future__ import annotations

from typing import assert_type

import bpy
from bpy.props import IntProperty, StringProperty
from bpy.types import Object, Scene

bpy.types.Scene.script_int = IntProperty()  # oracle-skip: the reference stubs declare it on the class


def setUp() -> None:
    bpy.types.Object.script_name = StringProperty()  # oracle-skip: the reference stubs declare it on the class


def tearDown() -> None:
    del bpy.types.Object.script_name
    del bpy.types.Scene.script_int


def register_startup() -> None:
    # The stubs, generated from a running Blender, already declare what its startup scripts register.
    bpy.types.WindowManager.preset_name = StringProperty()  # oracle-skip: the bpy stubs declare it as a plain `str`
    bpy.types.Object.pass_index = StringProperty()  # ty: ignore[invalid-assignment]  # bare-ok: another type than the declared one stays an error


def reads(scene: Scene, obj: Object) -> None:
    assert_type(scene.script_int, int)
    assert_type(obj.script_name, str)
    scene.script_int = 2
    scene.script_int = "2"  # ty: ignore[invalid-assignment]
    obj.script_int  # ty: ignore[missing-attribute]  # bare-ok: registered on Scene only
    scene.script_shared  # ty: ignore[missing-attribute]  # bare-ok: registered by another file of no add-on
