# /// catalog
# title = "An internal operator"
# section = "idnames"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["assumptions"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's stubs type the callback's `context` as `Context | None`, so the read is reported on `None` instead of as an Assumption."
# "fake-bpy-module/5.2" = "These stubs type the callback's `context` as `Context | None`, so the read is reported on `None` instead of as an Assumption."
# ///
"""`"INTERNAL"` in `bl_options` hides an operator from the operator search, so in ordinary use only the add-on's own
button or key calls it, where the context has what it needs. The checker takes the context members it reads as not
`None` and reports each read as an Assumption: a script can still call it anywhere, and then the read fails. A member
its `poll` checks is narrowed by the poll instead."""

from bpy.types import Operator


class ShowSettings(Operator):
    bl_idname = "operators.show_settings"
    bl_label = "Show settings"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        print(context.object.name)  # ty: ignore[blender-assumed-internal-operator]
        return {"FINISHED"}
