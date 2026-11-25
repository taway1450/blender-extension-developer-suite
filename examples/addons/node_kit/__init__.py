"""Node Kit: a calculator node tree of its own, and helpers for the shader editor."""

from . import shader, tree, ui


def register():
    tree.register()
    shader.register()
    ui.register()


def unregister():
    ui.unregister()
    shader.unregister()
    tree.unregister()
