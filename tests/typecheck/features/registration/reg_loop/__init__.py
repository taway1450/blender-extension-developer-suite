"""Feature test: classes registered by looping over module-level sequences: a tuple, a list, a list extended at
module level (append and +=), a concatenation, unpacking and nested loops. reversed() in unregister()."""

import bpy
from bpy.types import Operator


class REG_LOOP_OT_tuple(Operator):
    bl_idname = "reg_loop.tuple"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REG_LOOP_OT_list(Operator):
    bl_idname = "reg_loop.list"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REG_LOOP_OT_appended(Operator):
    bl_idname = "reg_loop.appended"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REG_LOOP_OT_extended(Operator):
    bl_idname = "reg_loop.extended"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REG_LOOP_OT_concat(Operator):
    bl_idname = "reg_loop.concat"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REG_LOOP_OT_unpacked(Operator):
    bl_idname = "reg_loop.unpacked"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REG_LOOP_OT_nested_a(Operator):
    bl_idname = "reg_loop.nested_a"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REG_LOOP_OT_nested_b(Operator):
    bl_idname = "reg_loop.nested_b"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


TUPLE_CLASSES = (REG_LOOP_OT_tuple,)
LIST_CLASSES = [REG_LOOP_OT_list]
LIST_CLASSES.append(REG_LOOP_OT_appended)
LIST_CLASSES += [REG_LOOP_OT_extended]
CONCAT_CLASSES = () + (REG_LOOP_OT_concat,)
UNPACKED_CLASSES = (*CONCAT_CLASSES, REG_LOOP_OT_unpacked)
GROUPS = ((REG_LOOP_OT_nested_a,), [REG_LOOP_OT_nested_b])


def register():
    for cls in TUPLE_CLASSES:
        bpy.utils.register_class(cls)
    for cls in LIST_CLASSES:
        bpy.utils.register_class(cls)
    for cls in UNPACKED_CLASSES:  # includes the concatenated class
        bpy.utils.register_class(cls)
    for group in GROUPS:
        for cls in group:
            bpy.utils.register_class(cls)


def unregister():
    for group in reversed(GROUPS):
        for cls in reversed(group):
            bpy.utils.unregister_class(cls)
    for cls in reversed(UNPACKED_CLASSES):
        bpy.utils.unregister_class(cls)
    for cls in reversed(LIST_CLASSES):
        bpy.utils.unregister_class(cls)
    for cls in reversed(TUPLE_CLASSES):
        bpy.utils.unregister_class(cls)
