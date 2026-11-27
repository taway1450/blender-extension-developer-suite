# /// catalog
# title = "`execute` returns a set of result names"
# section = "callbacks"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["inheritance"]
# see = ["blender/source/blender/python/intern/bpy_rna.cc"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's stubs type the callback's `context` as `Context | None`, so the read of `context.object` is reported too."
# "fake-bpy-module/5.2" = "These stubs type the callback's `context` as `Context | None`, so the read of `context.object` is reported too."
# ///
"""`execute`, `invoke` and `modal` return a set of result names such as `{"FINISHED"}` or `{"CANCELLED"}`, and Blender
checks each name when the method returns: a misspelt one raises. The checker types an unannotated `execute` from
`Operator.execute`, so each name is checked against the allowed ones."""

from bpy.types import Operator


class Apply(Operator):
    bl_idname = "operators.apply"
    bl_label = "Apply"

    def execute(self, context):
        if context.object is None:
            return {"CANCELLED"}
        return {"FINSHED"}  # ty: ignore[invalid-explicit-return]
