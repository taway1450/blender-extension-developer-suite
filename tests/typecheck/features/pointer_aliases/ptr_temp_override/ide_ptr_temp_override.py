"""Hover shows a context member as the value `temp_override` passed."""

import bpy
from bpy.types import Area


def redraw(area: Area):
    with bpy.context.temp_override(area=area):
        bpy.context.area
        #           ^hover
