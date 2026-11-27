# /// catalog
# title = "An override without annotations"
# section = "overrides"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["inheritance"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's stubs type `execute`'s `context` as `Context | None`, so `context.scene` is reported."
# "fake-bpy-module/5.2" = "These stubs type `execute`'s `context` as `Context | None`, so `context.scene` is reported."
# ///
"""Add-ons write `def execute(self, context):` without annotations. The checker types the parameters of an override
of a Blender callback from the method it overrides, so `context` is a `Context`, and checks the value it returns
against the parent's return type."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import Context, Operator


class Report(Operator):
    bl_idname = "inheritance.report"
    bl_label = "Report"

    def execute(self, context):
        assert_type(context, Context)
        print(context.scene.name)
        return {"DONE"}  # ty: ignore[invalid-explicit-return]
