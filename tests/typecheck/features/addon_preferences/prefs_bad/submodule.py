"""In a submodule __name__ is not the addon's name, nor is the first component of an extension's module name
(`bl_ext`)."""

from bpy.props import IntProperty
from bpy.types import AddonPreferences


class PREFS_BAD_Submodule(AddonPreferences):
    bl_idname = __name__  # ty: ignore[blender-preferences-idname]

    value: IntProperty()


class PREFS_BAD_FirstComponent(AddonPreferences):
    bl_idname = __name__.split(".")[0]  # ty: ignore[blender-preferences-idname]

    value: IntProperty()
