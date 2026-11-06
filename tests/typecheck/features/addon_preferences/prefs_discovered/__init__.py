"""Feature test: register() picks its preferences class at runtime, by name from globals(), so the checker cannot
follow it: addons[__package__].preferences is either class whose bl_idname names the add-on. Blender registers the
one the environment picks."""

import os

import bpy
from bpy.props import IntProperty, StringProperty
from bpy.types import AddonPreferences


class PREFS_DISCOVERED_Simple(AddonPreferences):
    bl_idname = __package__

    level: IntProperty()


class PREFS_DISCOVERED_Full(AddonPreferences):
    bl_idname = __package__

    path: StringProperty()


def _chosen():
    name = "PREFS_DISCOVERED_Full" if os.environ.get("PREFS_DISCOVERED_FULL") else "PREFS_DISCOVERED_Simple"
    return globals()[name]


def register():
    bpy.utils.register_class(_chosen())


def unregister():
    bpy.utils.unregister_class(_chosen())
