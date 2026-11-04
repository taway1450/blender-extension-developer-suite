"""Feature test: the first of two extensions in one workspace."""

import bpy
from bpy.props import IntProperty

from .values import START


def register():
    bpy.types.Scene.ws_value = IntProperty(default=START)
    bpy.types.Scene.ws_alpha_only = IntProperty()


def unregister():
    del bpy.types.Scene.ws_alpha_only
    del bpy.types.Scene.ws_value
