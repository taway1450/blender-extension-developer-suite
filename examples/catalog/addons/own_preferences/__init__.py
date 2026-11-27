# /// catalog
# title = "The add-on's own preferences"
# section = "preferences"
# status = "handled"
# handled-by = ["typechecker"]
# features = ["addon_preferences"]
# ///
"""`preferences.addons[__package__].preferences` is the add-on's own `AddonPreferences` subclass when the key names
the add-on, not the stub's `AddonPreferences | None`."""

# catalog: hide
from typing import assert_type

# catalog: show
import bpy
from bpy.props import FloatProperty
from bpy.types import AddonPreferences, Context


class OWN_PREFERENCES_Preferences(AddonPreferences):
    bl_idname = __package__

    scale: FloatProperty(default=1.0)


def scale(context: Context) -> float:
    preferences = context.preferences.addons[__package__].preferences
    # catalog: hide
    assert_type(preferences, OWN_PREFERENCES_Preferences)
    # catalog: show
    return preferences.scale


def register():
    bpy.utils.register_class(OWN_PREFERENCES_Preferences)


def unregister():
    bpy.utils.unregister_class(OWN_PREFERENCES_Preferences)
