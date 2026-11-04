"""Feature test: addon operators in a category Blender already has (object) sit next to the built-in operators,
and several operators can share a new category."""

import bpy
from bpy.props import FloatProperty
from bpy.types import Operator


class OBJECT_OT_opcall_category_scale(Operator):
    bl_idname = "object.opcall_category_scale"
    bl_label = "Scale"

    factor: FloatProperty()

    def execute(self, context):
        return {"FINISHED"}


class OPCALL_CATEGORY_OT_first(Operator):
    bl_idname = "opcall_category.first"
    bl_label = "First"

    def execute(self, context):
        return {"FINISHED"}


class OPCALL_CATEGORY_OT_second(Operator):
    bl_idname = "opcall_category.second"
    bl_label = "Second"

    def execute(self, context):
        return {"FINISHED"}


classes = (OBJECT_OT_opcall_category_scale, OPCALL_CATEGORY_OT_first, OPCALL_CATEGORY_OT_second)
register, unregister = bpy.utils.register_classes_factory(classes)
