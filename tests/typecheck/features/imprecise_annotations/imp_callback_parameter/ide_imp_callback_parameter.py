"""Hover shows the annotated subclass on a narrowed callback parameter."""

from bpy.types import Armature, UIList


class _Hover(UIList):
    def draw_item(self, context, layout, data: Armature, item, icon, active_data, active_property):
        data.name
#       ^hover-contains "Armature"
