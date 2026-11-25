"""Batch Export and Import: export every object to its own file, and import many files at once."""

import os

import bpy

from . import export, handlers, importer, settings, ui
from .translations import TRANSLATIONS

addon_keymaps = []


def register_keymap():
    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is None:  # background mode has no key configurations
        return
    keymap = keyconfig.keymaps.new(name="Object Mode")
    item = keymap.keymap_items.new(
        "export_scene.batch_export", "E", "PRESS", ctrl=True, shift=True
    )
    # demo: operator_properties
    item.properties.use_selection = True
    addon_keymaps.append((keymap, item))


def unregister_keymap():
    for keymap, item in addon_keymaps:
        keymap.keymap_items.remove(item)
    addon_keymaps.clear()


def register():
    settings.register()
    export.register()
    importer.register()
    ui.register()
    handlers.register()
    register_keymap()
    bpy.utils.register_preset_path(os.path.dirname(__file__))
    bpy.app.translations.register(__name__, TRANSLATIONS)


def unregister():
    bpy.app.translations.unregister(__name__)
    bpy.utils.unregister_preset_path(os.path.dirname(__file__))
    unregister_keymap()
    handlers.unregister()
    ui.unregister()
    importer.unregister()
    export.unregister()
    settings.unregister()
