"""The add-on's preferences."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, IntProperty
from bpy.types import AddonPreferences, Context


class ScatterToolsPreferences(AddonPreferences):
    bl_idname = __package__

    default_count: IntProperty(
        name="Default Count",
        description="Count the Scatter operator's redo panel starts with",
        default=10,
        min=1,
        max=1000,
    )
    show_stats: BoolProperty(
        name="Report Statistics",
        description="Report what a scatter run created",
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "default_count")
        layout.prop(self, "show_stats")


# demo: addon_preferences
def get_preferences(context: Context) -> ScatterToolsPreferences:
    return context.preferences.addons[__package__].preferences


def register() -> None:
    bpy.utils.register_class(ScatterToolsPreferences)


def unregister() -> None:
    bpy.utils.unregister_class(ScatterToolsPreferences)
