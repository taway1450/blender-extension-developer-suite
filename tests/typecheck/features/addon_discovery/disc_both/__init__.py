"""Feature test: blender_manifest.toml and bl_info both present. The manifest wins: this is an extension."""

import bpy
from bpy.props import StringProperty

bl_info = {
    "name": "Feature test: leftover bl_info",
    "version": (0, 1, 0),
    "blender": (2, 80, 0),
    "category": "Development",
}


def register():
    bpy.types.Scene.disc_both_marker = StringProperty()


def unregister():
    del bpy.types.Scene.disc_both_marker
