"""Feature test: register() calls bpy.utils.register_class directly, through a from-import and through an alias.
Operators show up in bpy.ops, properties assigned in register() on the class they are assigned to."""

import bpy
from bpy.props import IntProperty
from bpy.types import Operator
from bpy.utils import register_class, unregister_class
from bpy.utils import register_class as add_class


class REG_EXPLICIT_OT_dotted(Operator):
    bl_idname = "reg_explicit.dotted"
    bl_label = "Run"

    count: IntProperty()

    def execute(self, context):
        return {"FINISHED"}


class REG_EXPLICIT_OT_imported(Operator):
    bl_idname = "reg_explicit.imported"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REG_EXPLICIT_OT_alias(Operator):
    bl_idname = "reg_explicit.alias"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REG_EXPLICIT_OT_never(Operator):  # ty: ignore[blender-unregistered-class]
    bl_idname = "reg_explicit.never"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(REG_EXPLICIT_OT_dotted)
    register_class(REG_EXPLICIT_OT_imported)
    add_class(REG_EXPLICIT_OT_alias)
    bpy.types.Scene.reg_explicit_count = IntProperty()


def unregister():
    del bpy.types.Scene.reg_explicit_count
    unregister_class(REG_EXPLICIT_OT_alias)
    unregister_class(REG_EXPLICIT_OT_imported)
    bpy.utils.unregister_class(REG_EXPLICIT_OT_dotted)
