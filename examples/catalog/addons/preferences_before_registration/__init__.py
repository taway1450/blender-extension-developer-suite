# /// catalog
# title = "Preferences read before they are registered"
# section = "preferences"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["assumptions", "addon_preferences"]
#
# [differs]
# "builtin/5.2" = "`context.preferences` is `Preferences | None` in Blender 5.2's stubs, and `addons.get()` gives a plain `bpy_struct` there, which has no `preferences`."
# "fake-bpy-module/5.2" = "`context.preferences` is `Preferences | None` in these stubs, so the read is reported."
# ///
"""Blender adds the add-on's entry to `preferences.addons` before it calls `register()`, but the entry's
`preferences` stay `None` until the preferences class is registered. The checker still types them as the add-on's
class there and reports the read as an Assumption, since the code relies on the class being registered; after
`register_class` it says nothing."""

import bpy
from bpy.props import BoolProperty
from bpy.types import AddonPreferences


class PREFERENCES_BEFORE_REGISTRATION_Preferences(AddonPreferences):
    bl_idname = __package__

    use_keymap: BoolProperty(default=True)


def register():
    entry = bpy.context.preferences.addons.get(__package__)
    if entry is not None:
        print(entry.preferences.use_keymap)  # ty: ignore[blender-assumed-preferences]
    bpy.utils.register_class(PREFERENCES_BEFORE_REGISTRATION_Preferences)
    if entry is not None:
        print(entry.preferences.use_keymap)


def unregister():
    bpy.utils.unregister_class(PREFERENCES_BEFORE_REGISTRATION_Preferences)
