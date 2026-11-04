"""Imports the addon's top-level modules and registers the Blender classes defined in them (a reduced version of
the common auto_load.py)."""

import importlib
import inspect
import pkgutil

import bpy

classes = []


def init():
    package = importlib.import_module(__package__)
    for info in pkgutil.iter_modules(package.__path__):
        if info.name == "auto_load" or info.name.startswith(("check_", "ide_")):
            continue
        module = importlib.import_module(f"{__package__}.{info.name}")
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, bpy.types.bpy_struct) and cls.__module__ == module.__name__:
                classes.append(cls)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
