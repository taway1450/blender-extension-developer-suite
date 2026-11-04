"""Feature test: functions registered as application handlers and timers, with the handlers module imported in
different ways. @persistent keeps the function as it is (at runtime it returns the function)."""

import bpy
import bpy.app.handlers as handlers
from bpy.app.handlers import persistent


@persistent
def on_load_post(filepath, _unused):
    # load_post handlers are called with two arguments: the file path and None.
    pass


@bpy.app.handlers.persistent
def on_save_pre(*args):
    pass


def on_frame_change(scene, depsgraph):
    pass


def tick():
    return 1.0  # seconds until the next call; None stops the timer


def register():
    handlers.load_post.append(on_load_post)
    bpy.app.handlers.save_pre.append(on_save_pre)
    bpy.app.handlers.frame_change_post.append(on_frame_change)
    bpy.app.timers.register(tick, first_interval=0.5)


def unregister():
    bpy.app.timers.unregister(tick)
    bpy.app.handlers.frame_change_post.remove(on_frame_change)
    bpy.app.handlers.save_pre.remove(on_save_pre)
    handlers.load_post.remove(on_load_post)
