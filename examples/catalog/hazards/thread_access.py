# /// catalog
# title = "`bpy` in a thread"
# section = "threads"
# status = "not-handled"
# blender-docs = ["info_gotchas_threading"]
#
# [future]
# class = "not-checkable"
# note = "Whether a thread still runs when Blender draws, renders or evaluates drivers is known only while Blender runs."
# ///
"""Blender's Python is not thread-safe: a thread that still runs after the script returns can crash Blender later, in
its drawing, a render or a driver. A thread is fine only while the script waits for it with `join()`; for work apart
from Blender, Blender's docs advise `multiprocessing`."""

import threading

import bpy


def count_objects() -> None:
    print(len(bpy.data.objects))


def count_and_wait() -> None:
    thread = threading.Thread(target=count_objects)
    thread.start()
    thread.join()  # the thread ends before the script does


def count_in_background() -> None:
    threading.Thread(target=count_objects).start()  # may crash Blender later
