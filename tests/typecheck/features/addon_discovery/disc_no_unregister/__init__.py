"""Feature test: an extension with register() but no unregister()."""  # ty: ignore[blender-invalid-register]

import bpy
from bpy.props import IntProperty


def register():
    bpy.types.Scene.disc_no_unregister_marker = IntProperty()
