"""Feature test: register_classes_factory results called from a hand-written register(), next to other work."""

import bpy
from bpy.props import StringProperty
from bpy.types import Operator


class REG_FACTORY_OT_first(Operator):
    bl_idname = "reg_factory.first"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REG_FACTORY_OT_second(Operator):
    bl_idname = "reg_factory.second"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REG_FACTORY_OT_tools(Operator):
    bl_idname = "reg_factory.tools"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


_register, _unregister = bpy.utils.register_classes_factory((REG_FACTORY_OT_first, REG_FACTORY_OT_second))
register_tools, unregister_tools = bpy.utils.register_classes_factory([REG_FACTORY_OT_tools])


def register():
    _register()
    register_tools()
    bpy.types.Scene.reg_factory_label = StringProperty()


def unregister():
    del bpy.types.Scene.reg_factory_label
    unregister_tools()
    _unregister()
