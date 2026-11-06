"""Feature test: registration code that registers each class once on every path, so no rule reports it: a class
registered in a branch that returns and again after that branch, a list rebound in a branch, a tuple concatenated
onto itself, and a helper that calls itself with other keyword arguments. The class that is never registered shows
that the walk understood all of it: on a walk that gives up, blender-unregistered-class stays silent."""

import os

import bpy
from bpy.types import Operator


class REGCHK_PATHS_OT_early(Operator):
    bl_idname = "regchk_paths.early"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_PATHS_OT_rebound_a(Operator):
    bl_idname = "regchk_paths.rebound_a"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_PATHS_OT_rebound_b(Operator):
    bl_idname = "regchk_paths.rebound_b"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_PATHS_OT_concat_a(Operator):
    bl_idname = "regchk_paths.concat_a"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_PATHS_OT_concat_b(Operator):
    bl_idname = "regchk_paths.concat_b"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_PATHS_OT_keyword_a(Operator):
    bl_idname = "regchk_paths.keyword_a"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_PATHS_OT_keyword_b(Operator):
    bl_idname = "regchk_paths.keyword_b"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_PATHS_OT_never(Operator):  # ty: ignore[blender-unregistered-class]
    bl_idname = "regchk_paths.never"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


REBOUND = [REGCHK_PATHS_OT_rebound_a]
if os.environ.get("REGCHK_PATHS_MORE"):
    REBOUND = [REGCHK_PATHS_OT_rebound_a, REGCHK_PATHS_OT_rebound_b]

CONCAT = (REGCHK_PATHS_OT_concat_a,)
CONCAT = CONCAT + (REGCHK_PATHS_OT_concat_b,)


def _register_early():
    if os.environ.get("REGCHK_PATHS_EARLY"):
        bpy.utils.register_class(REGCHK_PATHS_OT_early)
        return
    bpy.utils.register_class(REGCHK_PATHS_OT_early)


def _register_chain(*, cls, then=None):
    bpy.utils.register_class(cls)
    if then is not None:
        _register_chain(cls=then)


def register():
    _register_early()
    for cls in REBOUND:
        bpy.utils.register_class(cls)
    for cls in CONCAT:
        bpy.utils.register_class(cls)
    _register_chain(cls=REGCHK_PATHS_OT_keyword_a, then=REGCHK_PATHS_OT_keyword_b)


def unregister():
    bpy.utils.unregister_class(REGCHK_PATHS_OT_keyword_b)
    bpy.utils.unregister_class(REGCHK_PATHS_OT_keyword_a)
    for cls in reversed(CONCAT):
        bpy.utils.unregister_class(cls)
    for cls in reversed(REBOUND):
        bpy.utils.unregister_class(cls)
    bpy.utils.unregister_class(REGCHK_PATHS_OT_early)
