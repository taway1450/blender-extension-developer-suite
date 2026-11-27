# /// catalog
# title = "An operator idname Blender rejects"
# section = "idnames"
# status = "handled"
# safeguards = ["typechecker", "blender-runtime"]
# features = ["registration_checks"]
#
# [evidence]
# addon = "registration_checks/regchk_idname"
# register = "fails"
# says = "invalid operator bl_idname"
# ///
"""An operator's `bl_idname` is `category.name` in lower-case letters, digits and underscores; it becomes
`bpy.ops.category.name`. Blender refuses any other form when the class is registered, the class-name form
`OBJECT_OT_run` included, and an operator without `bl_idname` gets its class name, which fails too. The checker
reports each."""

import bpy
from bpy.types import Operator

bl_info = {
    "name": "Catalog: an operator idname Blender rejects",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


class OPERATOR_IDNAME_OT_valid(Operator):
    bl_idname = "operator_idname.valid_name_2"
    bl_label = "Valid"

    def execute(self, context):
        return {"FINISHED"}


class OPERATOR_IDNAME_OT_class_form(Operator):
    bl_idname = "OPERATOR_IDNAME_OT_class_form"  # ty: ignore[blender-invalid-idname]
    bl_label = "Class form"

    def execute(self, context):
        return {"FINISHED"}


class OPERATOR_IDNAME_OT_dash(Operator):
    bl_idname = "operator_idname.has-dash"  # ty: ignore[blender-invalid-idname]
    bl_label = "Dash"

    def execute(self, context):
        return {"FINISHED"}


class OPERATOR_IDNAME_OT_missing(Operator):  # ty: ignore[blender-invalid-idname]
    bl_label = "Missing"

    def execute(self, context):
        return {"FINISHED"}


classes = (OPERATOR_IDNAME_OT_valid, OPERATOR_IDNAME_OT_class_form, OPERATOR_IDNAME_OT_dash, OPERATOR_IDNAME_OT_missing)
register, unregister = bpy.utils.register_classes_factory(classes)
