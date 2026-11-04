"""Feature test: register() reaches register_class through helper functions in the same file, nested helpers,
another module's register(), a loop over modules, a loop over functions and a static method."""

import bpy
from bpy.props import FloatProperty
from bpy.types import Operator

from . import loop_a, loop_b, tools


class REG_DELEGATION_OT_helper(Operator):
    bl_idname = "reg_delegation.helper"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REG_DELEGATION_OT_nested(Operator):
    bl_idname = "reg_delegation.nested"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REG_DELEGATION_OT_function_loop(Operator):
    bl_idname = "reg_delegation.function_loop"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REG_DELEGATION_OT_static_method(Operator):
    bl_idname = "reg_delegation.static_method"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def _register_helper():
    bpy.utils.register_class(REG_DELEGATION_OT_helper)


def _register_inner():
    bpy.utils.register_class(REG_DELEGATION_OT_nested)
    bpy.types.Scene.reg_delegation_factor = FloatProperty()


def _register_outer():
    _register_inner()


def _register_function_loop():
    bpy.utils.register_class(REG_DELEGATION_OT_function_loop)


class Registrar:
    @staticmethod
    def register():
        bpy.utils.register_class(REG_DELEGATION_OT_static_method)

    @staticmethod
    def unregister():
        bpy.utils.unregister_class(REG_DELEGATION_OT_static_method)


MODULES = (loop_a, loop_b)


def register():
    _register_helper()
    _register_outer()
    tools.register()
    for module in MODULES:
        module.register()
    for function in (_register_function_loop,):
        function()
    Registrar.register()


def unregister():
    Registrar.unregister()
    bpy.utils.unregister_class(REG_DELEGATION_OT_function_loop)
    for module in reversed(MODULES):
        module.unregister()
    tools.unregister()
    del bpy.types.Scene.reg_delegation_factor
    bpy.utils.unregister_class(REG_DELEGATION_OT_nested)
    bpy.utils.unregister_class(REG_DELEGATION_OT_helper)
