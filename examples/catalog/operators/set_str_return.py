# /// catalog
# title = "`-> set[str]` on `execute`"
# section = "callbacks"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["imprecise_annotations"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's stubs type the callback's `context` as `Context | None`, so the read of `context.object` is reported too."
# "fake-bpy-module/5.2" = "These stubs type the callback's `context` as `Context | None`, so the read of `context.object` is reported too."
# ///
"""The result names exist as `Literal` types only in the stubs, so add-ons often annotate `execute` with
`-> set[str]`. That is right in Blender but less precise than the parent's type. The checker accepts it, reports it as
an Imprecise annotation, and still checks each name returned."""

from bpy.types import Operator


class Apply(Operator):
    bl_idname = "operators.apply_set"
    bl_label = "Apply"

    def execute(self, context) -> set[str]:  # ty: ignore[blender-imprecise-operator-return]
        if context.object is None:
            return {"CANCELLED"}
        return {"FINSHED"}  # ty: ignore[invalid-explicit-return]
