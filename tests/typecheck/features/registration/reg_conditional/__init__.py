"""Feature test: classes registered only under a condition: a Blender version check (in register() and at module
level), a try block, hasattr on bpy.types and an environment variable. They may be registered, so they count."""

import os

import bpy
from bpy.types import Operator


class REG_CONDITIONAL_OT_version(Operator):
    bl_idname = "reg_conditional.version"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REG_CONDITIONAL_OT_module_version(Operator):
    bl_idname = "reg_conditional.module_version"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REG_CONDITIONAL_OT_try_block(Operator):
    bl_idname = "reg_conditional.try_block"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REG_CONDITIONAL_OT_hasattr(Operator):
    bl_idname = "reg_conditional.hasattr"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REG_CONDITIONAL_OT_environment(Operator):
    bl_idname = "reg_conditional.environment"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


classes = []
if bpy.app.version >= (4, 2, 0):
    classes.append(REG_CONDITIONAL_OT_module_version)


def register():
    if bpy.app.version >= (4, 2, 0):
        bpy.utils.register_class(REG_CONDITIONAL_OT_version)
    for cls in classes:
        bpy.utils.register_class(cls)
    try:
        bpy.utils.register_class(REG_CONDITIONAL_OT_try_block)
    except ValueError:
        pass
    if hasattr(bpy.types, "Strip"):
        bpy.utils.register_class(REG_CONDITIONAL_OT_hasattr)
    if os.environ.get("REG_CONDITIONAL_SKIP") is None:
        bpy.utils.register_class(REG_CONDITIONAL_OT_environment)


def unregister():
    for cls in [REG_CONDITIONAL_OT_environment, REG_CONDITIONAL_OT_hasattr, REG_CONDITIONAL_OT_try_block,
                *reversed(classes), REG_CONDITIONAL_OT_version]:
        if cls.is_registered:
            bpy.utils.unregister_class(cls)
