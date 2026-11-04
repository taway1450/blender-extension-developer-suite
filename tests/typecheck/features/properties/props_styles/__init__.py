"""Feature test: property annotations written in different ways (see the modules)."""

import bpy

from . import future_annotations, inheritance, plain_annotations

modules = (plain_annotations, future_annotations, inheritance)


def register():
    for module in modules:
        for cls in module.classes:
            bpy.utils.register_class(cls)


def unregister():
    for module in reversed(modules):
        for cls in reversed(module.classes):
            bpy.utils.unregister_class(cls)
