"""Feature test: blender-duplicate-registration. Registering a class twice fails (ValueError: already registered),
whether both calls are explicit, one is in a loop or the class is in the sequence twice. Two classes with the same
bl_idname register, but the second silently replaces the first."""

import bpy
from bpy.types import Operator


class REGCHK_DUPLICATE_OT_twice(Operator):
    bl_idname = "regchk_duplicate.twice"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_DUPLICATE_OT_loop(Operator):
    bl_idname = "regchk_duplicate.loop"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_DUPLICATE_OT_sequence(Operator):
    bl_idname = "regchk_duplicate.sequence"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_DUPLICATE_OT_first(Operator):
    bl_idname = "regchk_duplicate.same"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_DUPLICATE_OT_second(Operator):
    bl_idname = "regchk_duplicate.same"  # ty: ignore[blender-duplicate-registration]
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


classes = (
    REGCHK_DUPLICATE_OT_loop,
    REGCHK_DUPLICATE_OT_sequence,
    REGCHK_DUPLICATE_OT_sequence,  # ty: ignore[blender-duplicate-registration]
    REGCHK_DUPLICATE_OT_first,
    REGCHK_DUPLICATE_OT_second,
)


def register():
    bpy.utils.register_class(REGCHK_DUPLICATE_OT_twice)
    bpy.utils.register_class(REGCHK_DUPLICATE_OT_twice)  # ty: ignore[blender-duplicate-registration]
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.utils.register_class(REGCHK_DUPLICATE_OT_loop)  # ty: ignore[blender-duplicate-registration]


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    bpy.utils.unregister_class(REGCHK_DUPLICATE_OT_twice)
