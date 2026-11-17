"""Hover shows the space an area's type test narrows `spaces.active` to."""

from bpy.types import Screen


def view(screen: Screen):
    for area in screen.areas:
        if area.type == "VIEW_3D":
            area.spaces.active
            #           ^hover
