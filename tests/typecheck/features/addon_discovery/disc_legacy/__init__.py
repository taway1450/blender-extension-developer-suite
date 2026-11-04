"""Feature test: a legacy add-on package, found by bl_info (no blender_manifest.toml)."""

import bpy
from bpy.props import IntProperty

bl_info = {
    "name": "Feature test: legacy add-on",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "Nowhere",
    "description": "A legacy add-on package with bl_info",
    "category": "Development",
}


def register():
    bpy.types.Scene.disc_legacy_marker = IntProperty()


def unregister():
    del bpy.types.Scene.disc_legacy_marker
