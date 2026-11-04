"""In a submodule __name__ is not the addon's name."""

from bpy.props import IntProperty
from bpy.types import AddonPreferences


class PREFS_BAD_Submodule(AddonPreferences):
    bl_idname = __name__  # ty: ignore[blender-preferences-idname]

    value: IntProperty()
