"""Not an add-on (no manifest, no bl_info): a script like a test or a doc example, which registers a property that
only its own file reads."""

import bpy
from bpy.props import IntProperty

bpy.types.Scene.script_shared = IntProperty()
