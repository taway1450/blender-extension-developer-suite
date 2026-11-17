"""Hover shows the type an assumed context member is narrowed to outside a callback."""

import bpy


def helper():
    bpy.context.scene
    #           ^hover
