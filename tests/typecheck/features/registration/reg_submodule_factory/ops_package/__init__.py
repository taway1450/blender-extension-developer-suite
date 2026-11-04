"""A subpackage registered by register_submodule_factory; it delegates to its own module."""

from . import operators


def register():
    operators.register()


def unregister():
    operators.unregister()
