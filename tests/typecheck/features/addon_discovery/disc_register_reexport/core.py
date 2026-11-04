"""The add-on's real entry points."""

import bpy
from bpy.props import BoolProperty


def register():
    bpy.types.Scene.disc_register_reexport_marker = BoolProperty()


def unregister():
    del bpy.types.Scene.disc_register_reexport_marker
