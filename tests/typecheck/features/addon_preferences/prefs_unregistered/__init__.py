"""Feature test: an AddonPreferences class that is never registered is not the addon's preferences."""

from bpy.props import IntProperty
from bpy.types import AddonPreferences


class PREFS_UNREGISTERED_Preferences(AddonPreferences):  # ty: ignore[blender-unregistered-class]
    bl_idname = __package__

    value: IntProperty()


def register():
    pass


def unregister():
    pass
