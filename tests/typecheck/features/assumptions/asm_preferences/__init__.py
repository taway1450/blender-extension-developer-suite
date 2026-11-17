"""Feature test: `addons[__package__].preferences` is the add-on's preferences class only while that class is
registered. register() runs with the add-on's entry already there but its `preferences` None until
register_class(Preferences), and so does unregister() after unregister_class(Preferences). The checker keeps the class
type and reports such a read under blender-assumed-preferences; a read after registering, or in a callback, is not
reported."""

from typing import assert_type

import bpy
from bpy.props import BoolProperty
from bpy.types import AddonPreferences, Operator


class ASM_PREFERENCES_Preferences(AddonPreferences):
    bl_idname = __package__

    use_keymap: BoolProperty(default=True)


class ASM_PREFERENCES_OT_run(Operator):
    bl_idname = "asm_preferences.run"
    bl_label = "Run"

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences  # a callback: not reported
        assert_type(prefs, ASM_PREFERENCES_Preferences)
        return {"FINISHED"}


def setup_keymap():
    entry = bpy.context.preferences.addons.get(__package__)
    if entry is not None:
        print(entry.preferences.use_keymap)  # registered by then: not reported


def read_early():
    entry = bpy.context.preferences.addons.get(__package__)
    if entry is not None:
        print(entry.preferences)  # ty: ignore[blender-assumed-preferences]


def register():
    entry = bpy.context.preferences.addons.get(__package__)  # the entry exists while Blender enables the add-on
    if entry is not None:
        early = entry.preferences  # ty: ignore[blender-assumed-preferences]
        assert_type(early, ASM_PREFERENCES_Preferences)
    read_early()
    bpy.utils.register_class(ASM_PREFERENCES_Preferences)
    bpy.utils.register_class(ASM_PREFERENCES_OT_run)
    setup_keymap()


def unregister():
    bpy.utils.unregister_class(ASM_PREFERENCES_OT_run)
    bpy.utils.unregister_class(ASM_PREFERENCES_Preferences)
    entry = bpy.context.preferences.addons.get(__package__)
    if entry is not None:
        print(entry.preferences is None)  # ty: ignore[blender-assumed-preferences]
