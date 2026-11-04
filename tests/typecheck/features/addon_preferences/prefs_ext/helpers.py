"""A direct submodule: its package name is __name__ without the last part."""

from bpy.types import Preferences


def preferences(preferences: Preferences):
    return preferences.addons[__name__.rpartition(".")[0]].preferences


def register():
    pass


def unregister():
    pass
