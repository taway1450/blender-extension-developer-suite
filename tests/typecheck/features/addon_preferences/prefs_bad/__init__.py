"""Feature test: blender-preferences-idname. Blender finds an addon's preferences by bl_idname; these classes
register (checked in Blender 5.4) but are never the addon's preferences: a wrong literal, __name__ in a submodule,
no bl_idname, and a second class for the same addon (it silently replaces the first)."""

import bpy
from bpy.props import IntProperty
from bpy.types import AddonPreferences

from . import submodule


class PREFS_BAD_Wrong(AddonPreferences):
    bl_idname = "not_this_addon"  # ty: ignore[blender-preferences-idname]

    value: IntProperty()


class PREFS_BAD_Missing(AddonPreferences):  # ty: ignore[blender-preferences-idname]
    value: IntProperty()


class PREFS_BAD_First(AddonPreferences):
    bl_idname = __package__

    value: IntProperty()


class PREFS_BAD_Second(AddonPreferences):
    bl_idname = __package__  # ty: ignore[blender-preferences-idname]

    other: IntProperty()


classes = (PREFS_BAD_Wrong, PREFS_BAD_Missing, PREFS_BAD_First, PREFS_BAD_Second, submodule.PREFS_BAD_Submodule)
register, unregister = bpy.utils.register_classes_factory(classes)
