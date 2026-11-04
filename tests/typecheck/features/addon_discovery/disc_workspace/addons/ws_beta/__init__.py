"""Feature test: the second of two extensions in one workspace."""

import bpy
from bpy.props import StringProperty


def register():
    bpy.types.Scene.ws_value = StringProperty()


def unregister():
    del bpy.types.Scene.ws_value
