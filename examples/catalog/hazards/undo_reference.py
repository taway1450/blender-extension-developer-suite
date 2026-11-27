# /// catalog
# title = "A reference kept across undo"
# section = "stale-data"
# status = "not-handled"
# blender-docs = ["info_gotchas_crashes", "info_gotchas_internal_data_and_python_objects"]
#
# [future]
# class = "not-checkable"
# note = "Whether the data a reference points to still exists depends on what the user undoes while Blender runs."
#
# [differs]
# "builtin/5.2" = "Blender 5.2's stubs type the callback's `context` as `Context | None`, so every read of it is reported, and `bpy.data.scenes.get` returns a plain `bpy_struct`, not `Scene | None`."
# "fake-bpy-module/5.2" = "These stubs type the callback's `context` as `Context | None`, so every read of it is reported."
# ///
"""Undo and redo may free every data-block and its sub-data, and a Python object that still points to one then reads
freed memory, which can crash Blender. Blender's docs advise to keep no reference to Blender data between
operators: keep a name or an index and look the data up again."""

import bpy
from bpy.types import Operator, Scene

REMEMBERED: dict[str, Scene] = {}
SCENE_NAMES: list[str] = []


class SIMPLE_OT_remember(Operator):
    bl_idname = "simple.remember"
    bl_label = "Remember"

    def execute(self, context):
        REMEMBERED["last"] = context.scene  # may point to freed data after an undo
        SCENE_NAMES.append(context.scene.name)  # a name stays valid
        return {"FINISHED"}


def last_scene() -> Scene | None:
    return bpy.data.scenes.get(SCENE_NAMES[-1]) if SCENE_NAMES else None
