"""A package that imports its submodules by name, as Blender's `bl_ui` and `bl_operators` do: `__import__` binds
each submodule the list names in the package."""

from typing import Literal, assert_type

if "bpy" in locals():
    from importlib import reload

    _modules_loaded[:] = [reload(val) for val in _modules_loaded]
    del reload

_modules = [
    "panels",
]

import bpy

if bpy.app.version >= (4, 2, 0):
    _modules.append("extra")

__import__(name=__name__, fromlist=_modules)
_namespace = globals()
_modules_loaded = [_namespace[name] for name in _modules]
del _namespace


def register():
    assert_type(panels.LABEL, Literal["Panels"])
    assert_type(extra.LABEL, Literal["Extra"])
    panels.register()


def unregister():
    panels.unregister()


def _unlisted():
    return unlisted  # ty: ignore[unresolved-reference]  # bare-ok: a submodule the list does not name is not imported
