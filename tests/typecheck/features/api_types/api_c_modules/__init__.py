"""Feature test: Blender's private C modules. `_cycles`, `_bpy` and `_bpy_hydra` have no API docs, so their stubs are
partial (every member is Any); `_freestyle` holds the C classes and functions that the documented `freestyle.*`
modules re-export, so its stub re-exports them and they keep their types. The stubs must state it
(check_api_c_modules.py); the helpers below compute the facts for the runtime probes (_expected/runtime.toml)."""

import importlib

import bpy

FREESTYLE_MODULES = ("types", "predicates", "functions", "chainingiterators", "shaders", "utils")


def c_modules():
    """The type names of the private C modules, imported."""
    names = ("_cycles", "_bpy", "_bpy_hydra", "_freestyle")
    return " ".join(type(importlib.import_module(name)).__name__ for name in names)


def freestyle_undocumented():
    """The public members of `_freestyle` that no documented `freestyle.*` module re-exports as the same object."""
    import _freestyle

    modules = [importlib.import_module("freestyle." + name) for name in FREESTYLE_MODULES]
    names = [
        name
        for name, value in vars(_freestyle).items()
        if not name.startswith("_") and not any(getattr(module, name, None) is value for module in modules)
    ]
    return " ".join(sorted(names))


def register():
    pass


def unregister():
    pass
