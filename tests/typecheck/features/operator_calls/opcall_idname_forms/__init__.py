"""Feature test: bl_idname values the checker has to evaluate: a module constant, a concatenation, an f-string of
constants, a class attribute of another class and a value inherited from a mixin. An idname only known at runtime
gives no bpy.ops attribute."""

import os

import bpy
from bpy.types import Operator

CATEGORY = "opcall_idname_forms"
CONSTANT_IDNAME = "opcall_idname_forms.constant"


class Run:
    def execute(self, context):
        return {"FINISHED"}


class IdnameMixin:
    bl_idname = "opcall_idname_forms.from_mixin"


class OPCALL_IDNAME_FORMS_OT_constant(Run, Operator):
    bl_idname = CONSTANT_IDNAME
    bl_label = "Constant"


class OPCALL_IDNAME_FORMS_OT_concat(Run, Operator):
    bl_idname = CATEGORY + ".concat"
    bl_label = "Concat"


class OPCALL_IDNAME_FORMS_OT_fstring(Run, Operator):
    bl_idname = f"{CATEGORY}.fstring"
    bl_label = "F-string"


class OPCALL_IDNAME_FORMS_OT_attribute(Run, Operator):
    bl_idname = OPCALL_IDNAME_FORMS_OT_fstring.bl_idname + "_copy"
    bl_label = "Attribute"


class OPCALL_IDNAME_FORMS_OT_mixin(Run, IdnameMixin, Operator):
    bl_label = "Mixin"


class OPCALL_IDNAME_FORMS_OT_runtime(Run, Operator):
    bl_idname = os.environ.get("OPCALL_IDNAME_FORMS", "opcall_idname_forms.runtime")
    bl_label = "Runtime"


classes = (OPCALL_IDNAME_FORMS_OT_constant, OPCALL_IDNAME_FORMS_OT_concat, OPCALL_IDNAME_FORMS_OT_fstring,
           OPCALL_IDNAME_FORMS_OT_attribute, OPCALL_IDNAME_FORMS_OT_mixin, OPCALL_IDNAME_FORMS_OT_runtime)
register, unregister = bpy.utils.register_classes_factory(classes)
