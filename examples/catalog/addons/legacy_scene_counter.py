# /// catalog
# title = "A legacy single-file add-on"
# section = "metadata"
# status = "handled"
# handled-by = ["typechecker"]
# features = ["addon_discovery", "properties"]
# ///
"""A module with a `bl_info` dict is a legacy add-on. Its `register()` adds a Registered property, which the rest of
the add-on reads with its Value type."""

# catalog: hide
from typing import assert_type

# catalog: show
import bpy
from bpy.props import IntProperty

bl_info = {
    "name": "Scene counter",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


def register():
    bpy.types.Scene.counter = IntProperty()


def unregister():
    del bpy.types.Scene.counter


def bump(scene: bpy.types.Scene) -> None:
    # catalog: hide
    assert_type(scene.counter, int)
    # catalog: show
    scene.counter += 1
