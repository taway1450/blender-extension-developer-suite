"""Feature test: a Macro operator. Its call takes one keyword argument per step operator, named by the step's
OT idname, holding a dict of the step's properties (checked in Blender 5.4). define() returns an OperatorMacro."""

import bpy
from bpy.props import IntProperty, StringProperty
from bpy.types import Macro, Operator


class OPCALL_MACRO_OT_step(Operator):
    bl_idname = "opcall_macro.step"
    bl_label = "Step"
    bl_options = {"REGISTER", "UNDO"}

    amount: IntProperty()

    def execute(self, context):
        return {"FINISHED"}


class OPCALL_MACRO_OT_label(Operator):
    bl_idname = "opcall_macro.label"
    bl_label = "Label"
    bl_options = {"REGISTER", "UNDO"}

    text: StringProperty()

    def execute(self, context):
        return {"FINISHED"}


class OPCALL_MACRO_OT_combo(Macro):
    bl_idname = "opcall_macro.combo"
    bl_label = "Combo"
    bl_options = {"REGISTER", "UNDO"}


def register():
    bpy.utils.register_class(OPCALL_MACRO_OT_step)
    bpy.utils.register_class(OPCALL_MACRO_OT_label)
    bpy.utils.register_class(OPCALL_MACRO_OT_combo)
    OPCALL_MACRO_OT_combo.define("OPCALL_MACRO_OT_step")
    OPCALL_MACRO_OT_combo.define("opcall_macro.label")


def unregister():
    bpy.utils.unregister_class(OPCALL_MACRO_OT_combo)
    bpy.utils.unregister_class(OPCALL_MACRO_OT_label)
    bpy.utils.unregister_class(OPCALL_MACRO_OT_step)
