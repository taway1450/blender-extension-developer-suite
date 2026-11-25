"""Export on save. The save handler only starts a timer, so the export runs after the save has finished."""

import bpy
from bpy.app.handlers import persistent


# demo: bpy_symbols
# demo: later/handler-callback-types
@persistent
def export_after_save(filepath, *_):
    scene = bpy.context.scene
    wanted = filepath and scene.batch_export_and_import.export_on_save
    if wanted and not bpy.app.timers.is_registered(run_export):
        bpy.app.timers.register(run_export, first_interval=0.5)


# A timer runs again after the seconds it returns; this one returns nothing, so it runs once.
def run_export():
    if bpy.context.mode == "OBJECT":
        bpy.ops.export_scene.batch_export(use_selection=False)


def register():
    bpy.app.handlers.save_post.append(export_after_save)


def unregister():
    bpy.app.handlers.save_post.remove(export_after_save)
    if bpy.app.timers.is_registered(run_export):
        bpy.app.timers.unregister(run_export)
