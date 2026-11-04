"""Feature test: an add-on package declared in pyproject.toml ([tool.blender] addons)."""

import bpy
from bpy.props import FloatProperty


def register():
    bpy.types.Scene.disc_override_marker = FloatProperty()


def unregister():
    del bpy.types.Scene.disc_override_marker
