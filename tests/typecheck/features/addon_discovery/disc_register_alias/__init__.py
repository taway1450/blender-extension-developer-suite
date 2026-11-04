"""Feature test: register and unregister are names bound to other functions."""

import bpy
from bpy.props import StringProperty


def _register_all():
    bpy.types.Scene.disc_register_alias_marker = StringProperty()


def _unregister_all():
    del bpy.types.Scene.disc_register_alias_marker


register = _register_all
unregister = _unregister_all
