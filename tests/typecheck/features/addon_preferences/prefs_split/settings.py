"""The preferences class, named by the first component of this submodule's name."""

from bpy.props import FloatProperty
from bpy.types import AddonPreferences


class PREFS_SPLIT_Preferences(AddonPreferences):
    bl_idname = __name__.split(".")[0]

    scale: FloatProperty(default=1.0)
