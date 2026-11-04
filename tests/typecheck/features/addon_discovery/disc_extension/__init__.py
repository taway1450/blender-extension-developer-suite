"""Feature test: an extension, found by the blender_manifest.toml next to this file."""

import bpy
from bpy.props import IntProperty

from .sub import helpers


def register():
    bpy.types.Scene.disc_extension_marker = IntProperty(default=helpers.DEFAULT)


def unregister():
    del bpy.types.Scene.disc_extension_marker
